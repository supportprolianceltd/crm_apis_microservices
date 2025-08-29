default_templates = {
    'interviewScheduling': {
        'content': (
            'Hello [Candidate Name],\n\n'
            'We’re pleased to invite you to an interview for the [Position] role at [Company].\n'
            'Please let us know your availability so we can confirm a convenient time.\n\n'
            'Best regards,\n[Your Name]'
        ),
        'is_auto_sent': False
    },
    'interviewRescheduling': {
        'content': (
            'Hello [Candidate Name],\n\n'
            'Due to unforeseen circumstances, we need to reschedule your interview originally set for [Old Date/Time]. '
            'Kindly share a few alternative slots that work for you.\n\n'
            'Thanks for your understanding,\n[Your Name]'
        ),
        'is_auto_sent': False
    },
    'interviewRejection': {
        'content': (
            'Hello [Candidate Name],\n\n'
            'Thank you for taking the time to interview. After careful consideration, '
            'we have decided not to move forward.\n\n'
            'Best wishes,\n[Your Name]'
        ),
        'is_auto_sent': False
    },
    'interviewAcceptance': {
        'content': (
            'Hello [Candidate Name],\n\n'
            'Congratulations! We are moving you to the next stage. We’ll follow up with next steps.\n\n'
            'Looking forward,\n[Your Name]'
        ),
        'is_auto_sent': False
    },
    'jobRejection': {
        'content': (
            'Hello [Candidate Name],\n\n'
            'Thank you for applying. Unfortunately, we’ve chosen another candidate at this time.\n\n'
            'Kind regards,\n[Your Name]'
        ),
        'is_auto_sent': False
    },
    'jobAcceptance': {
        'content': (
            'Hello [Candidate Name],\n\n'
            'We’re excited to offer you the [Position] role at [Company]! '
            'Please find the offer letter attached.\n\n'
            'Welcome aboard!\n[Your Name]'
        ),
        'is_auto_sent': False
    },
    'shortlistedNotification': {
        'content': (
            'Hello [Candidate Name],\n\n'
            'Congratulations! You have been shortlisted for the [Position] role at [Company].\n\n'
            '[Employment Gaps]\n\n'
            'We will contact you soon with further details.\n\n'
            'Best regards,\n[Your Name]'
        ),
        'is_auto_sent': False
    }
}