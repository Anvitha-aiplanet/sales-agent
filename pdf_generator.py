from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import black
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import re


def convert_markdown_formatting(text):
    """Convert markdown formatting to ReportLab's internal formatting"""
    # Convert bold text (both ** and __)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
    
    # Convert italic text (both * and _) - using non-greedy match for better accuracy
    text = re.sub(r'\*([^*]+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'_([^_]+?)_', r'<i>\1</i>', text)
    
    # Convert inline code
    text = re.sub(r'`([^`]+?)`', r'<code>\1</code>', text)
    
    return text

def ensure_balanced_tags(text):
    """Ensure that HTML-style tags are properly balanced"""
    # Check for basic tag balance
    tags_to_check = ['i', 'b', 'code']
    
    for tag in tags_to_check:
        opening_count = text.count(f'<{tag}>')
        closing_count = text.count(f'</{tag}>')
        
        # Add missing closing tags
        if opening_count > closing_count:
            text += f'</{tag}>' * (opening_count - closing_count)
        
        # Remove extra closing tags or add missing opening tags
        elif closing_count > opening_count:
            # Find position of first unmatched closing tag
            positions = []
            depth = 0
            
            for i in range(len(text)):
                if text[i:i+len(f'<{tag}>')] == f'<{tag}>':
                    depth += 1
                elif text[i:i+len(f'</{tag}>')] == f'</{tag}>':
                    depth -= 1
                    if depth < 0:
                        positions.append(i)
                        depth = 0
            
            # Remove unmatched closing tags
            for pos in sorted(positions, reverse=True):
                text = text[:pos] + text[pos+len(f'</{tag}>'):]
    
    return text

def fix_html_content(text):
    """Fix common HTML formatting issues that could cause ReportLab errors"""
    # First, remove any existing para tags as we'll handle paragraphs differently
    text = text.replace('<para>', '').replace('</para>', '')
    
    # Fix issues with unbalanced italic tags
    open_i_count = text.count('<i>')
    close_i_count = text.count('</i>')
    
    if open_i_count > close_i_count:
        # Add missing closing tags
        text += '</i>' * (open_i_count - close_i_count)
    
    # Fix issues with unbalanced bold tags
    open_b_count = text.count('<b>')
    close_b_count = text.count('</b>')
    
    if open_b_count > close_b_count:
        # Add missing closing tags
        text += '</b>' * (open_b_count - close_b_count)
    
    # Fix issues with unbalanced code tags
    open_code_count = text.count('<code>')
    close_code_count = text.count('</code>')
    
    if open_code_count > close_code_count:
        # Add missing closing tags
        text += '</code>' * (open_code_count - close_code_count)
    
    return text


# def convert_markdown_formatting(text):
#     """Convert markdown formatting to ReportLab's internal formatting"""
#     # Convert numbered lists first
#     text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
    
#     # Convert bold text (both ** and __)
#     text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
#     text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
    
#     # Convert italic text (both * and _)
#     text = re.sub(r'\*([^*]+?)\*', r'<i>\1</i>', text)
#     text = re.sub(r'_([^_]+?)_', r'<i>\1</i>', text)
    
#     # Convert inline code
#     text = re.sub(r'`([^`]+?)`', r'<code>\1</code>', text)
    
#     # Clean up any nested tags that might cause issues
#     text = re.sub(r'<([bi])>([^<]*?)<([bi])>([^<]*?)</\3>([^<]*?)</\1>', 
#                   r'<\1>\2\4\5</\1><\3>\4</\3>', text)
    
#     return text

def clean_markdown_for_pdf(markdown_text):
    """Clean and structure markdown content for PDF while preserving formatting"""
    # First convert inline formatting
    text = convert_markdown_formatting(markdown_text)
    
    # Split into sections based on headers
    sections = re.split(r'(####?\s*[^\n]+)', text)
    
    # Handle the case when there are no section headers
    if not sections or (len(sections) == 1 and not sections[0].strip().startswith('#')):
        # No headers found, treat the entire text as one section
        sections = ["### Document", text]
    else:
        # Remove any content before the first header
        if sections and not sections[0].strip().startswith('#'):
            sections = sections[1:]
    
    structured_content = []
    
    for i in range(0, len(sections), 2):
        header = sections[i].strip('#').strip()
        content = sections[i + 1].strip() if i + 1 < len(sections) else ""
        
        # Process content into paragraphs and bullets
        lines = content.split('\n')
        processed_paragraphs = []
        current_bullets = []
        
        current_paragraph = []
        
        for line in lines:
            line = line.strip()
            if line.startswith(('- ', '• ', '* ')):
                # If we have accumulated paragraph lines, add them first
                if current_paragraph:
                    processed_paragraphs.append(' '.join(current_paragraph))
                    current_paragraph = []
                
                bullet_text = line.replace('- ', '').replace('• ', '').replace('* ', '').strip()
                current_bullets.append(bullet_text)
            elif line:
                # If we have accumulated bullets, add them first
                if current_bullets:
                    structured_content.append({
                        'type': 'bullets',
                        'content': current_bullets.copy()
                    })
                    current_bullets = []
                
                current_paragraph.append(line)
            else:
                # Empty line - break paragraph
                if current_paragraph:
                    processed_paragraphs.append(' '.join(current_paragraph))
                    current_paragraph = []
        
        # Add any remaining paragraph lines
        if current_paragraph:
            processed_paragraphs.append(' '.join(current_paragraph))
        
        # Add header
        structured_content.append({
            'type': 'header',
            'content': header,
            'level': len(re.match(r'#+', sections[i]).group()) if re.match(r'#+', sections[i]) else 3
        })
        
        # Add any remaining bullets
        if current_bullets:
            structured_content.append({
                'type': 'bullets',
                'content': current_bullets
            })
        
        # Add processed paragraphs
        for para in processed_paragraphs:
            structured_content.append({
                'type': 'paragraph',
                'content': para
            })
    
    return structured_content
def create_formatted_pdf(markdown_content):
    """Create well-formatted PDF with proper styling and formatting"""
    buffer = io.BytesIO()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    styles = getSampleStyleSheet()
    
    # Enhanced styles with support for bold, italic, and code formatting
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        spaceAfter=30,
        spaceBefore=12,
        leading=32
    )
    
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        spaceBefore=12,
        leading=24,
        textColor=black
    )
    
    subsection_style = ParagraphStyle(
        'SubsectionHeader',
        parent=styles['Heading3'],
        fontSize=14,
        spaceAfter=8,
        spaceBefore=8,
        leading=20
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=8,
        spaceBefore=8,
        leading=14
    )
    
    bullet_style = ParagraphStyle(
        'CustomBullet',
        parent=styles['Normal'],
        fontSize=12,
        leftIndent=20,
        firstLineIndent=0,
        spaceAfter=6,
        spaceBefore=6,
        bulletIndent=12,
        leading=14
    )
    
    # Style for code sections
    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Code'],
        fontSize=10,
        fontName='Courier',
        spaceAfter=8,
        spaceBefore=8,
        leading=12,
        backColor='#f5f5f5'
    )
    
    elements = []
    structured_content = clean_markdown_for_pdf(markdown_content)
    
    first_header = True
    
    for item in structured_content:
        if item['type'] == 'header':
            if first_header:
                elements.append(Paragraph(item['content'], title_style))
                first_header = False
            else:
                style = section_style if item['level'] == 3 else subsection_style
                elements.append(Spacer(1, 12))
                elements.append(Paragraph(item['content'], style))
        
        elif item['type'] == 'bullets':
            bullet_list = []
            for bullet in item['content']:
                # Fix any HTML formatting issues before creating paragraph
                fixed_bullet = fix_html_content(bullet)
                try:
                    bullet_para = Paragraph(fixed_bullet, bullet_style)
                    bullet_list.append(ListItem(
                        bullet_para,
                        leftIndent=20,
                        value='•'
                    ))
                except Exception as e:
                    # If bullet conversion fails, try with plain text
                    print(f"Warning: Could not create bullet with formatting: {e}")
                    plain_bullet = re.sub(r'<[^>]+>', '', fixed_bullet)
                    bullet_para = Paragraph(plain_bullet, bullet_style)
                    bullet_list.append(ListItem(
                        bullet_para,
                        leftIndent=20,
                        value='•'
                    ))
            
            elements.append(ListFlowable(
                bullet_list,
                bulletType='bullet',
                leftIndent=20,
                bulletFontSize=12,
                start='•',
                spaceBefore=6,
                spaceAfter=6
            ))
        
        elif item['type'] == 'paragraph':
            # Fix any HTML formatting issues before creating paragraph
            fixed_para = fix_html_content(item['content'])
            try:
                elements.append(Paragraph(fixed_para, body_style))
            except Exception as e:
                # If paragraph conversion fails, try with plain text
                print(f"Warning: Could not create paragraph with formatting: {e}")
                plain_para = re.sub(r'<[^>]+>', '', fixed_para)
                elements.append(Paragraph(plain_para, body_style))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer