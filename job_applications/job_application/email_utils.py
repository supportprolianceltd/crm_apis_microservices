import logging
from django.core.mail import EmailMessage
from core.utils.email_config import configure_email_backend
import logging
import logging
from django.core.mail import EmailMessage
from core.models import TenantConfig

logger = logging.getLogger('job_applications')

def send_rejection_emails(tenant, job_requisition, applications):
    try:
        tenant_config = TenantConfig.objects.get(tenant=tenant)
        email_config = tenant_config.email_templates.get('interviewRejection', {})
        
        if not email_config.get('is_auto_sent', False):
            logger.info(f"Auto-send not enabled for interviewRejection template for tenant {tenant.schema_name}")
            return

        email_template = email_config.get('content', '')
        if not email_template:
            logger.warning(f"No email template content found for interviewRejection for tenant {tenant.schema_name}")
            return

        email_backend = configure_email_backend(tenant)
        for app in applications:
            if app.status == 'rejected':
                try:
                    email_content = email_template
                    email_content = email_content.replace('[Candidate Name]', app.full_name)
                    email_content = email_content.replace('[Job Title]', job_requisition.title)
                    email_content = email_content.replace('[Your Name]', 'Hiring Manager')
                    email_content = email_content.replace('[your.email@proliance.com]', tenant.default_from_email or 'hiring@proliance.com')

                    email = EmailMessage(
                        subject=f'Application Update for {job_requisition.title} at Proliance',
                        body=email_content,
                        from_email=tenant.default_from_email or 'hiring@proliance.com',
                        to=[app.email],
                        connection=email_backend
                    )
                    email.send()
                    logger.info(f"Rejection email sent to {app.email} for JobRequisition {job_requisition.id}")
                except Exception as e:
                    logger.error(f"Failed to send rejection email to {app.email}: {str(e)}")
    except TenantConfig.DoesNotExist:
        logger.error(f"Tenant configuration not found for tenant {tenant.schema_name}")
    except Exception as e:
        logger.error(f"Error in send_rejection_emails for tenant {tenant.schema_name}: {str(e)}")


def send_shortlisted_emails(tenant, job_requisition, applications):
    try:
        tenant_config = TenantConfig.objects.get(tenant=tenant)
        email_config = tenant_config.email_templates.get('shortlistedNotification', {})
        
        if not email_config.get('is_auto_sent', False):
            logger.info(f"Auto-send not enabled for shortlistedNotification template for tenant {tenant.schema_name}")
            return

        email_template = email_config.get('content', '')
        if not email_template:
            logger.warning(f"No email template content found for shortlistedNotification for tenant {tenant.schema_name}")
            return

        email_backend = configure_email_backend(tenant)
        for app in applications:
            if app.status == 'shortlisted':
                try:
                    email_content = email_template
                    email_content = email_content.replace('[Candidate Name]', app.full_name)
                    email_content = email_content.replace('[Job Title]', job_requisition.title)
                    email_content = email_content.replace('[Your Name]', 'Hiring Manager')
                    email_content = email_content.replace('[your.email@proliance.com]', tenant.default_from_email or 'hiring@proliance.com')

                    # Only add [Employment Gaps] if there are gaps
                    if app.employment_gaps:
                        gaps_info = "We noticed the following employment gaps in your resume:\n"
                        for gap in app.employment_gaps:
                            gaps_info += f"- From {gap['gap_start']} to {gap['gap_end']} ({gap['duration_months']} months)\n"
                        gaps_info += "Please be prepared to discuss these during the interview process."
                        email_content = email_content.replace('[Employment Gaps]', gaps_info)
                    else:
                        # Remove the placeholder if present
                        email_content = email_content.replace('[Employment Gaps]', '')

                    email = EmailMessage(
                        subject=f'Shortlisted for {job_requisition.title} at Proliance',
                        body=email_content,
                        from_email=tenant.default_from_email or 'hiring@proliance.com',
                        to=[app.email],
                        connection=email_backend
                    )
                    email.send()
                    logger.info(f"Shortlisted email sent to {app.email} for JobRequisition {job_requisition.id}")
                except Exception as e:
                    logger.error(f"Failed to send shortlisted email to {app.email}: {str(e)}")
    except TenantConfig.DoesNotExist:
        logger.error(f"Tenant configuration not found for tenant {tenant.schema_name}")
    except Exception as e:
        logger.error(f"Error in send_shortlisted_emails for tenant {tenant.schema_name}: {str(e)}")