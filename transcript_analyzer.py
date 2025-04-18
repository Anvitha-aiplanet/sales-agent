import os
from openai import AzureOpenAI
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import streamlit as st
import uuid
import google.generativeai as genai

class TranscriptAnalyzer:
    def __init__(self, deployment_name):
        """Initialize the TranscriptAnalyzer with Azure OpenAI credentials."""
        self.client = AzureOpenAI(
            azure_endpoint=st.secrets.get("AZURE_OPENAI_ENDPOINT"),
            api_key=st.secrets.get("AZURE_OPENAI_API_KEY"),
            api_version=st.secrets.get("AZURE_OPENAI_API_VERSION")
        )
        self.deployment_name = deployment_name
        
        # Initialize Gemini if API key is available
        gemini_api_key = st.secrets.get("GOOGLE_API_KEY")
        self.gemini_available = False
        
        if gemini_api_key:
            try:
                genai.configure(api_key=gemini_api_key)
                self.gemini_available = True
                # Default model - can be 'gemini-pro' or other versions
                self.gemini_model_name = "gemini-2.0-flash"
                self.gemini_model = genai.GenerativeModel(self.gemini_model_name)
            except Exception as e:
                print(f"Error configuring Gemini: {str(e)}")
    
    def analyze_transcript(self, transcript, temperature=0.3):
        """Analyze a transcript to identify potential follow-up actions."""

        system_prompt = """
        You are an expert assistant that analyzes client conversation transcripts.
        Identify specific follow-up actions needed based on the transcript.
        
        For each follow-up, provide:
        1. A clear description of the follow-up action
        2. The priority level (High, Medium, Low)
        3. A brief justification for the follow-up
        4. Any relevant dates, numbers, or specific details mentioned
        
        Format your response as JSON with the following structure:
        {
            "follow_ups": [
                {
                    "action": "description of follow-up action",
                    "priority": "High|Medium|Low",
                    "justification": "reason for follow-up",
                    "details": "relevant specifics"
                }
            ],
            "summary": "brief summary of the key points from the conversation"
        }
        
        If no follow-ups are needed, return an empty list for follow_ups.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Here is the client transcript to analyze:\n\n{transcript}"}
                ],
                temperature=temperature,
                response_format={"type": "json_object"}
            )
            
            # Extract the response content
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            return {"error": str(e)}
    
    def get_structured_follow_ups(self, transcript):
        """Get a structured list of follow-ups from a transcript."""

        analysis = self.analyze_transcript(transcript)
        
        if "error" in analysis:
            return {"status": "error", "message": analysis["error"]}
        
        # Count follow-ups by priority
        priority_counts = {"High": 0, "Medium": 0, "Low": 0}
        if "follow_ups" in analysis:
            for item in analysis["follow_ups"]:
                if item["priority"] in priority_counts:
                    priority_counts[item["priority"]] += 1
        
        result = {
            "status": "success",
            "follow_ups": analysis.get("follow_ups", []),
            "summary": analysis.get("summary", ""),
            "priority_counts": priority_counts,
            "total_follow_ups": len(analysis.get("follow_ups", []))
        }
        print("RESULTS", result)
        return result
    
    def generate_email_draft_with_gemini(self, follow_up_info, transcript_id=None, feedback=None):
        """Generate an email draft using Google's Gemini model"""
        if not self.gemini_available:
            st.warning("Gemini not configured. Falling back to Azure OpenAI.")
            return self.generate_email_draft(follow_up_info, transcript_id, feedback)
            
        try:
            # If no transcript ID, generate one
            if not transcript_id:
                transcript_id = f"TRANSCRIPT-{uuid.uuid4().hex[:8]}"
            
            # Generate ticket ID
            ticket_id = f"{transcript_id}-{datetime.now().strftime('%Y%m%d%H%M')}"
            
            # Determine overall priority based on highest priority follow-up
            priority = "normal"
            if follow_up_info["priority_counts"]["High"] > 0:
                priority = "urgent"
            elif follow_up_info["priority_counts"]["Medium"] > 0:
                priority = "high"
            
            # Create the prompt for Gemini
            prompt = f"""You are an expert assistant that drafts professional follow-up emails to be sent to clients.
            Create a well-structured, professional client-facing email that addresses the follow-up actions needed.
            
            The email should:
            1. Have an appropriate subject line
            2. Include a professional greeting
            3. Have a brief introduction recapping the conversation
            4. Clearly outline next steps and any information needed from the client
            5. Include clear action items and deadlines without mentioning "priority levels"
            6. End with a professional closing
            
            The tone should be professional, helpful, and client-oriented. Do not mention internal tracking details like ticket IDs or priority ratings.
            
            Format your response with:
            Subject: [Your subject line here]
            
            [Body of the email]
            
            Here's the information about the conversation:
            
            Summary of conversation:
            {follow_up_info["summary"]}
            
            Follow-up actions required ({follow_up_info["total_follow_ups"]} total):
            """
            
            # Add each follow-up item to the prompt, but format for client-facing email
            for idx, item in enumerate(follow_up_info["follow_ups"], 1):
                # Remove internal priority markers and justifications for client email
                prompt += f"""
                {idx}. Action needed: {item["action"]}
                   Details: {item["details"]}
                """
            
            # If user provided feedback, add it to the prompt
            if feedback:
                prompt += f"\n\nIncorporate this feedback in your draft: {feedback}"
            
            # Generate response with Gemini
            response = self.gemini_model.generate_content(prompt)
            email_content = response.text
            
            # Extract subject line and body
            email_parts = email_content.split("Subject:", 1)
            
            if len(email_parts) > 1:
                # There is a subject line in the generated email
                subject_and_body = email_parts[1].strip()
                subject_body_split = subject_and_body.split("\n", 1)
                
                subject = subject_body_split[0].strip()
                body = subject_body_split[1].strip() if len(subject_body_split) > 1 else ""
            else:
                # No subject found, generate a default one
                subject = f"Follow-up from our recent conversation"
                body = email_content.strip()
            
            return {
                "subject": subject,
                "body": body,
                "ticket_id": ticket_id,
                "priority": priority,
                "model_used": "gemini"
            }
                
        except Exception as e:
            st.error(f"Error generating email draft with Gemini: {str(e)}")
            # Fall back to OpenAI
            return self.generate_email_draft(follow_up_info, transcript_id, feedback)
    
    def generate_email_draft(self, follow_up_info, transcript_id=None, feedback=None):
        """Generate an email draft based on follow-up information and optional feedback"""
        
        # Always try to use Gemini first if available
        if self.gemini_available:
            return self.generate_email_draft_with_gemini(follow_up_info, transcript_id, feedback)
            
        try:
            # If no transcript ID, generate one
            if not transcript_id:
                transcript_id = f"TRANSCRIPT-{uuid.uuid4().hex[:8]}"
            
            # Generate ticket ID
            ticket_id = f"{transcript_id}-{datetime.now().strftime('%Y%m%d%H%M')}"
            
            # Determine overall priority based on highest priority follow-up
            priority = "normal"
            if follow_up_info["priority_counts"]["High"] > 0:
                priority = "urgent"
            elif follow_up_info["priority_counts"]["Medium"] > 0:
                priority = "high"
                
            # Prepare the system prompt for email generation
            system_prompt = """
            You are an expert assistant that drafts professional follow-up emails based on client conversation analysis.
            Create a well-structured, professional email that addresses the follow-up actions identified.
            
            The email should:
            1. Have an appropriate subject line based on priority
            2. Include a professional greeting
            3. Have a brief introduction explaining the purpose of the email
            4. List each follow-up action clearly with its priority and justification
            5. Include a call to action appropriate for the priority level
            6. End with a professional closing
            
            The tone should be professional yet conversational and appropriate to the priority level.
            
            Format your response with:
            Subject: [Your subject line here]
            
            [Body of the email]
            """
            
            # If user provided feedback, add it to the prompt
            if feedback:
                system_prompt += f"\n\nIncorporate this feedback in your next draft: {feedback}"
            
            # Create the user prompt with structured data about follow-ups
            user_prompt = f"""
            Please draft a professional email based on the following follow-up information:
            
            Ticket ID: {ticket_id}
            Overall Priority: {priority.upper()}
            
            Summary of conversation:
            {follow_up_info["summary"]}
            
            Follow-up actions required ({follow_up_info["total_follow_ups"]} total):
            """
            
            # Add each follow-up item to the prompt
            for idx, item in enumerate(follow_up_info["follow_ups"], 1):
                user_prompt += f"""
                {idx}. Action: {item["action"]}
                   Priority: {item["priority"]}
                   Justification: {item["justification"]}
                   Details: {item["details"]}
                """
            
            # Call OpenAI to generate the email
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7
            )
            
            # Get the generated email content
            email_content = response.choices[0].message.content
            
            # Extract subject line and body (assuming the format includes "Subject:" somewhere)
            email_parts = email_content.split("Subject:", 1)
            
            if len(email_parts) > 1:
                # There is a subject line in the generated email
                subject_and_body = email_parts[1].strip()
                subject_body_split = subject_and_body.split("\n", 1)
                
                subject = subject_body_split[0].strip()
                body = subject_body_split[1].strip() if len(subject_body_split) > 1 else ""
            else:
                # No subject found, generate a default one
                if priority == "urgent":
                    subject = f"URGENT: Client Follow-up Required - Ticket #{ticket_id}"
                elif priority == "high":
                    subject = f"HIGH PRIORITY: Client Follow-up - Ticket #{ticket_id}"
                else:
                    subject = f"Client Follow-up - Ticket #{ticket_id}"
                
                body = email_content.strip()
            
            return {
                "subject": subject,
                "body": body,
                "ticket_id": ticket_id,
                "priority": priority,
                "model_used": "azure_openai"
            }
                
        except Exception as e:
            st.error(f"Error generating email draft: {str(e)}")
            return {
                "subject": f"Follow-up Required - Ticket #{transcript_id}",
                "body": f"Error generating email draft: {str(e)}",
                "ticket_id": transcript_id,
                "priority": "normal",
                "model_used": "error"
            }
    
    def send_email_alert(self, transcript_id, recipient_email, follow_up_info, email_config=None):
        """Send email alert for follow-up actions based on transcript analysis. """

        if not follow_up_info or follow_up_info.get("status") != "success" or not follow_up_info.get("follow_ups"):
            print("No follow-ups to send email about")
            return False
            
        try:
            # Default email config if none provided
            if not email_config:
                email_config = {
                    "smtp_server": os.environ.get("SMTP_SERVER", "smtp.gmail.com"),
                    "smtp_port": int(os.environ.get("SMTP_PORT", 587)),
                    "email_address": os.environ.get("EMAIL_ADDRESS", ""),
                    "email_password": os.environ.get("EMAIL_PASSWORD", "")
                }
            
            # Determine priority based on highest priority follow-up
            priority = "normal"
            if follow_up_info["priority_counts"]["High"] > 0:
                priority = "urgent"
            elif follow_up_info["priority_counts"]["Medium"] > 0:
                priority = "high"
            
            # Set up email
            msg = MIMEMultipart()
            msg['From'] = email_config["email_address"]
            msg['To'] = recipient_email
            
            # Set subject based on priority
            ticket_id = f"{transcript_id}-{datetime.now().strftime('%Y%m%d%H%M')}"
            if priority == "urgent":
                msg['Subject'] = f"URGENT: Client Follow-up Required - Ticket #{ticket_id}"
            elif priority == "high":
                msg['Subject'] = f"HIGH PRIORITY: Client Follow-up - Ticket #{ticket_id}"
            else:
                msg['Subject'] = f"Client Follow-up - Ticket #{ticket_id}"
            
            # Create email body
            ticket_type = ""
            action_message = ""
            
            if priority == "urgent":
                ticket_type = "URGENT FOLLOW-UP REQUIRED"
                action_message = "review this transcript and take immediate action"
            elif priority == "high":
                ticket_type = "HIGH PRIORITY FOLLOW-UP"
                action_message = "address these follow-up items as high priority"
            else:
                ticket_type = "FOLLOW-UP NEEDED"
                action_message = "address these follow-up items accordingly"
            
            # Format follow-up items as HTML
            follow_up_html = ""
            for idx, item in enumerate(follow_up_info["follow_ups"], 1):
                priority_color = "red" if item["priority"] == "High" else "orange" if item["priority"] == "Medium" else "green"
                follow_up_html += f"""
                <div style="margin-bottom: 15px; padding: 10px; border-left: 4px solid {priority_color};">
                  <h4>Follow-up #{idx}: <span style="color:{priority_color}">{item["priority"]}</span></h4>
                  <p><strong>Action needed:</strong> {item["action"]}</p>
                  <p><strong>Justification:</strong> {item["justification"]}</p>
                  <p><strong>Details:</strong> {item["details"]}</p>
                </div>
                """
            
            # Create email body
            body = f"""
            <html>
              <body>
                <h2>{ticket_type}</h2>
                <p>A client conversation transcript has been analyzed and requires follow-up action.</p>
                
                <h3>Ticket Information:</h3>
                <ul>
                  <li><strong>Ticket #:</strong> {ticket_id}</li>
                  <li><strong>Priority:</strong> <span style="color:{'red' if priority == 'urgent' else ('orange' if priority == 'high' else 'green')}"><strong>{priority.upper()}</strong></span></li>
                  <li><strong>Total follow-ups:</strong> {follow_up_info["total_follow_ups"]}</li>
                  <li><strong>High priority items:</strong> {follow_up_info["priority_counts"]["High"]}</li>
                  <li><strong>Medium priority items:</strong> {follow_up_info["priority_counts"]["Medium"]}</li>
                  <li><strong>Low priority items:</strong> {follow_up_info["priority_counts"]["Low"]}</li>
                </ul>
                
                <h3>Conversation Summary:</h3>
                <p>{follow_up_info["summary"]}</p>
                
                <h3>Required Follow-up Actions:</h3>
                {follow_up_html}
                
                <p>Please {action_message}.</p>
              </body>
            </html>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            # Setup SMTP server
            server = smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"])
            server.starttls()
            server.login(email_config["email_address"], email_config["email_password"])
            
            # Send email
            server.send_message(msg)
            server.quit()
            
            print(f"{priority.capitalize()} follow-up email alert sent to {recipient_email}")
            return True
            
        except Exception as e:
            print(f"Error sending follow-up email alert: {str(e)}")
            return False
    
    def send_custom_email(self, email_data, recipient_email, email_config=None):
        """Send a custom email with the provided content"""
        try:
            # Default email config if none provided
            if not email_config:
                email_config = {
                    "smtp_server": os.environ.get("SMTP_SERVER", "smtp.gmail.com"),
                    "smtp_port": int(os.environ.get("SMTP_PORT", 587)),
                    "email_address": st.secrets.get("EMAIL_ADDRESS", ""),
                    "email_password": st.secrets.get("EMAIL_PASSWORD", "")
                }
            
            # Set up email
            msg = MIMEMultipart()
            msg['From'] = email_config["email_address"]
            msg['To'] = recipient_email
            msg['Subject'] = email_data["subject"]
            
            # Convert plain text to HTML for better formatting
            html_body = email_data["body"].replace('\n', '<br>')
            msg.attach(MIMEText(html_body, 'html'))
            
            # Setup SMTP server
            server = smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"])
            server.starttls()
            server.login(email_config["email_address"], email_config["email_password"])
            
            # Send email
            server.send_message(msg)
            server.quit()
            
            return True
                
        except Exception as e:
            st.error(f"Error sending custom email: {str(e)}")
            return False