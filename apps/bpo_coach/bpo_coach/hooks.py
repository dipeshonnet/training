app_name = 'bpo_coach'
app_title = 'AI Coach'
app_publisher = 'Everyday AI'
app_description = 'Internal BPO training and AI simulations'
app_email = 'admin@everydayai.work'
app_license = 'AGPL-3.0-or-later'
required_apps = ['lms']
before_install = 'bpo_coach.install.ensure_roles'
after_install = 'bpo_coach.install.after_install'
after_migrate = 'bpo_coach.install.after_migrate'
before_request = ['bpo_coach.permissions.before_request']
website_route_rules = [{'from_route': '/coach/<path:app_path>', 'to_route': 'coach'}]
website_redirects = [{'source': '/', 'target': '/coach'}]
scheduler_events = {'all': ['bpo_coach.jobs.recover_grading', 'bpo_coach.jobs.reminders']}

_native = ['LMS Course', 'LMS Batch', 'Course Chapter', 'Course Lesson', 'LMS Course Progress', 'LMS Enrollment', 'LMS Certificate', 'LMS Quiz Submission', 'LMS Assignment Submission', 'File']
has_permission = {d: 'bpo_coach.permissions.native_permission' for d in _native}
_custom = ['BPO Client', 'BPO Process', 'BPO Process Access', 'AI Scenario', 'AI Scenario Version', 'AI Asset', 'BPO Training Assignment', 'AI Attempt', 'AI Action', 'AI Dialogue', 'AI Operation', 'AI Provider Settings', 'BPO Import Record', 'BPO Reminder']
has_permission.update({d: 'bpo_coach.permissions.custom_permission' for d in _custom})
permission_query_conditions = {d: 'bpo_coach.permissions.deny_query' for d in _custom}
permission_query_conditions['LMS Course'] = 'bpo_coach.permissions.course_query'
doc_events = {
    **{d: {'validate': 'bpo_coach.permissions.validate_scope', 'on_trash': 'bpo_coach.permissions.protect_delete'} for d in ['LMS Course', 'LMS Batch', 'Course Chapter', 'Course Lesson']},
    'LMS Course Progress': {'validate': 'bpo_coach.completion.validate_progress'},
    'LMS Certificate': {'validate': 'bpo_coach.completion.validate_certificate'},
    'File': {'validate': 'bpo_coach.permissions.validate_scope'},
}
