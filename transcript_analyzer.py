import os
from openai import AzureOpenAI
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import streamlit as st

class TranscriptAnalyzer:
    def __init__(self, deployment_name):
        """Initialize the TranscriptAnalyzer with Azure OpenAI credentials."""
        self.client = AzureOpenAI(
            azure_endpoint=st.secrets.get("AZURE_OPENAI_ENDPOINT"),
            api_key=st.secrets.get("AZURE_OPENAI_API_KEY"),
            api_version=st.secrets.get("AZURE_OPENAI_API_VERSION")
        )
        self.deployment_name = deployment_name
    
    def analyze_transcript(self, transcript, temperature=0.3):
        """
        Analyze a transcript to identify potential follow-up actions.
        
        Args:
            transcript (str): The client conversation transcript
            temperature (float): Controls randomness in the model's output
            
        Returns:
            dict: Analysis results containing follow-up actions
        """
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
        """
        Get a structured list of follow-ups from a transcript.
        
        Args:
            transcript (str): The client conversation transcript
            
        Returns:
            dict: Structured follow-up information
        """
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
        
        return result
        
    def send_email_alert(self, transcript_id, recipient_email, follow_up_info, email_config=None):
        """
        Send email alert for follow-up actions based on transcript analysis.
        
        Args:
            transcript_id (str): Unique identifier for the transcript
            recipient_email (str): Email address to send the alert to
            follow_up_info (dict): Follow-up information from get_structured_follow_ups
            email_config (dict, optional): Email configuration parameters
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
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


# Example usage
def main():
    # Load credentials from environment variables for security
    # azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    # api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    # api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2023-05-15")
    deployment_name ="intern-gpt4"
    
    # Email settings
    email_recipient = os.environ.get("EMAIL_RECIPIENT", "anvithareddy1308@gmail.com")
    
    # Check if credentials are available
    # if not all([azure_endpoint, api_key, deployment_name]):
    #     print("Error: Azure OpenAI credentials not found in environment variables")
    #     return
    
    # Example transcript
    sample_transcript = """
    Client: Hi, I'm interested in upgrading our current software package.
    Rep: That's great to hear. We have several options available. What specific features are you looking for?
    Client: Well, we need better reporting capabilities, and our team mentioned they'd like the new inventory management module.
    Rep: The premium package includes enhanced reporting. As for the inventory module, we can include that as an add-on.
    Client: That sounds promising. Could you send me a detailed quote by next Friday? I need to present it to the board on the 20th.
    Rep: Absolutely, I'll prepare that for you. By the way, would you be interested in our training program for the new features?
    Client: Maybe. Let's focus on the quote first, and we can discuss training options once the purchase is approved.
    Rep: Perfect. I'll send that quote by Friday. Is there anything else you need in the meantime?
    Client: Actually, I'm having some issues with our current system crashing when we run month-end reports.
    Rep: I'm sorry to hear that. Would you like me to have one of our technical specialists look into that for you?
    Client: Yes, that would be helpful. The sooner the better.
    Rep: I'll arrange that right away. Thanks for bringing this to our attention.
    """
    
    # Generate a unique ID for this transcript
    transcript_id = f"TRANSCRIPT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Create analyzer and process the transcript
    analyzer = TranscriptAnalyzer(deployment_name)
    results = analyzer.get_structured_follow_ups(sample_transcript)
    
    # Display results
    if results["status"] == "success":
        print(f"Transcript Analysis Results - Total Follow-ups: {results['total_follow_ups']}")
        print(f"Summary: {results['summary']}\n")
        
        print("Priority Counts:")
        for priority, count in results["priority_counts"].items():
            print(f"  - {priority}: {count}")
        
        print("\nFollow-up Actions:")
        for i, action in enumerate(results["follow_ups"], 1):
            print(f"\n{i}. {action['action']} (Priority: {action['priority']})")
            print(f"   Justification: {action['justification']}")
            print(f"   Details: {action['details']}")
            
        # Send email if follow-ups are needed
        if results["total_follow_ups"] > 0:
            # Email configuration - in production, these should be loaded from environment variables
            email_config = {
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "email_address": os.environ.get("EMAIL_ADDRESS", "anvitha@aiplanet.com"),
                "email_password": os.environ.get("EMAIL_PASSWORD", "drle ebzs hmbf fspw")
            }
            
            # Only attempt to send email if credentials are configured
            if email_config["email_address"] and email_config["email_password"]:
                email_sent = analyzer.send_email_alert(
                    transcript_id=transcript_id,
                    recipient_email=email_recipient,
                    follow_up_info=results,
                    email_config=email_config
                )
                if email_sent:
                    print(f"Follow-up email sent to {email_recipient}")
                else:
                    print("Failed to send follow-up email")
            else:
                print("Email credentials not configured. Set EMAIL_ADDRESS and EMAIL_PASSWORD environment variables.")
    else:
        print(f"Error: {results['message']}")


if __name__ == "__main__":
    main()