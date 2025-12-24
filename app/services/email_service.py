"""
Email service for sending voting receipts and notifications
"""
import os
from typing import Optional, Dict, Any
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

class EmailService:
    """Service for sending emails"""
    
    def __init__(self):
        # Configure your SMTP settings
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("FROM_EMAIL", "noreply@yourdomain.com")
        self.from_name = os.getenv("FROM_NAME", "Secure Voting System")
    
    def send_email(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send an email
        
        Args:
            to_email: Recipient email address
            to_name: Recipient name
            subject: Email subject
            html_content: HTML email content
            text_content: Plain text fallback
            
        Returns:
            bool: True if email sent successfully
        """
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = f"{to_name} <{to_email}>"
            
            # Add plain text version if provided
            if text_content:
                text_part = MIMEText(text_content, "plain")
                message.attach(text_part)
            
            # Add HTML version
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                server.send_message(message)
            
            print(f"✅ Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            print(f"❌ Error sending email: {str(e)}")
            return False
    
    def send_vote_receipt_email(
        self,
        user_email: str,
        user_name: str,
        vote_receipt: str,
        election_name: str,
        position_name: str,
        candidate_name: str,
        timestamp: str
    ) -> bool:
        """
        Send vote receipt email to user
        
        Args:
            user_email: User's email address
            user_name: User's full name
            vote_receipt: Vote receipt code
            election_name: Name of the election
            position_name: Position voted for
            candidate_name: Candidate voted for
            timestamp: When the vote was cast
            
        Returns:
            bool: True if email sent successfully
        """
        
        # Create HTML content
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                    border-radius: 10px 10px 0 0;
                }}
                .content {{
                    background: #f9f9f9;
                    padding: 30px;
                    border: 1px solid #ddd;
                }}
                .receipt-box {{
                    background: white;
                    border: 2px dashed #667eea;
                    border-radius: 10px;
                    padding: 20px;
                    margin: 20px 0;
                    text-align: center;
                }}
                .receipt-code {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #667eea;
                    letter-spacing: 2px;
                    padding: 15px;
                    background: #f0f0ff;
                    border-radius: 5px;
                    margin: 10px 0;
                }}
                .details {{
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                }}
                .detail-row {{
                    display: flex;
                    justify-content: space-between;
                    padding: 10px 0;
                    border-bottom: 1px solid #eee;
                }}
                .detail-label {{
                    font-weight: bold;
                    color: #666;
                }}
                .detail-value {{
                    color: #333;
                }}
                .footer {{
                    background: #333;
                    color: white;
                    padding: 20px;
                    text-align: center;
                    border-radius: 0 0 10px 10px;
                    font-size: 12px;
                }}
                .warning {{
                    background: #fff3cd;
                    border: 1px solid #ffc107;
                    border-radius: 5px;
                    padding: 15px;
                    margin: 20px 0;
                    color: #856404;
                }}
                .success {{
                    background: #d4edda;
                    border: 1px solid #28a745;
                    border-radius: 5px;
                    padding: 15px;
                    margin: 20px 0;
                    color: #155724;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🗳️ Vote Confirmation</h1>
                <p>Your vote has been securely recorded</p>
            </div>
            
            <div class="content">
                <p>Dear <strong>{user_name}</strong>,</p>
                
                <div class="success">
                    <strong>✅ Success!</strong> Your vote has been encrypted and securely stored in our system.
                </div>
                
                <div class="receipt-box">
                    <h3>Your Vote Receipt</h3>
                    <div class="receipt-code">{vote_receipt}</div>
                    <p style="font-size: 12px; color: #666; margin-top: 10px;">
                        Save this code to verify your vote anytime
                    </p>
                </div>
                
                <div class="details">
                    <h3 style="margin-top: 0;">Vote Details</h3>
                    
                    <div class="detail-row">
                        <span class="detail-label">Election:</span>
                        <span class="detail-value">{election_name}</span>
                    </div>
                    
                    <div class="detail-row">
                        <span class="detail-label">Position:</span>
                        <span class="detail-value">{position_name}</span>
                    </div>
                    
                    <div class="detail-row">
                        <span class="detail-label">Candidate:</span>
                        <span class="detail-value">{candidate_name}</span>
                    </div>
                    
                    <div class="detail-row" style="border-bottom: none;">
                        <span class="detail-label">Time:</span>
                        <span class="detail-value">{timestamp}</span>
                    </div>
                </div>
                
                <div class="warning">
                    <strong>⚠️ Important:</strong>
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li>Keep this receipt code safe and confidential</li>
                        <li>You can use it to verify your vote was counted</li>
                        <li>Your vote is anonymous and cannot be traced back to you</li>
                        <li>Do not share this receipt with anyone</li>
                    </ul>
                </div>
                
                <p style="text-align: center; margin-top: 30px;">
                    <strong>Thank you for participating in democracy!</strong>
                </p>
            </div>
            
            <div class="footer">
                <p>This is an automated message from the Secure Voting System</p>
                <p>© {datetime.now().year} Secure Voting System. All rights reserved.</p>
            </div>
        </body>
        </html>
        """
        
        # Plain text version
        text_content = f"""
        Vote Confirmation
        
        Dear {user_name},
        
        Your vote has been successfully recorded!
        
        VOTE RECEIPT: {vote_receipt}
        
        Vote Details:
        - Election: {election_name}
        - Position: {position_name}
        - Candidate: {candidate_name}
        - Time: {timestamp}
        
        IMPORTANT:
        - Keep this receipt code safe
        - Use it to verify your vote was counted
        - Your vote is anonymous and encrypted
        - Do not share this code with anyone
        
        Thank you for participating!
        
        ---
        Secure Voting System
        """
        
        return self.send_email(
            to_email=user_email,
            to_name=user_name,
            subject=f"Vote Receipt - {election_name}",
            html_content=html_content,
            text_content=text_content
        )

    def send_password_reset_email(self, user_email: str, user_name: str, reset_code: str) -> bool:
            """Sends a 6-digit OTP for password reset"""
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; border: 1px solid #eee; padding: 20px; border-radius: 10px;">
                        <h2 style="color: #764ba2; text-align: center;">Password Reset Request</h2>
                        <p>Hello <strong>{user_name}</strong>,</p>
                        <p>We received a request to reset your password. Use the code below to proceed:</p>
                        <div style="text-align: center; margin: 30px 0;">
                            <span style="font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #667eea; background: #f0f0ff; padding: 15px 30px; border-radius: 5px; border: 1px dashed #667eea;">
                                {reset_code}
                            </span>
                        </div>
                        <p>This code will expire in 10 minutes. If you did not request this, please ignore this email or contact support.</p>
                        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                        <p style="font-size: 12px; color: #999; text-align: center;">Secure Voting System &copy; {datetime.now().year}</p>
                    </div>
                </body>
            </html>
            """
            return self.send_email(
                to_email=user_email,
                to_name=user_name,
                subject="Your Password Reset Code",
                html_content=html_content,
                text_content=f"Your password reset code is: {reset_code}"
            )

# Create singleton instance
email_service = EmailService()