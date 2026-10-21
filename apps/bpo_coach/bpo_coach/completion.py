import json
import re
import frappe
from bpo_coach.engine import approved_channels
from bpo_coach.security import load_json

def blocks(lesson):
    content = load_json(lesson.content, {})
    return content.get('blocks', []) if isinstance(content, dict) else []

def bindings(lesson):
    result = []
    for index, block in enumerate(blocks(lesson)):
        if block.get('type') != 'ai_coach':
            continue
        data = block.get('data') or {}
        version = data.get('version')
        channels = data.get('channels', [])
        if not version or not channels or not isinstance(channels, list) or set(channels) - {'workflow', 'chat', 'voice'}:
            frappe.throw('AI Coach blocks need a published version and required channels.')
        if not frappe.db.exists('AI Scenario Version', version):
            frappe.throw('AI Coach version does not exist.')
        result.append({'lesson': lesson.name, 'activity': block.get('id') or str(index), 'version': version, 'channels': channels})
    return result

def course_lessons(course):
    return frappe.get_all('Course Lesson', filters={'course': course}, pluck='name', order_by='creation asc')

def assessment_ids(lesson):
    quizzes, assignments = set(), set()
    if lesson.quiz_id:
        quizzes.add(lesson.quiz_id)
    for block in blocks(lesson):
        data = block.get('data') or {}
        if block.get('type') == 'quiz' and data.get('quiz'):
            quizzes.add(data['quiz'])
        if block.get('type') == 'assignment' and data.get('assignment'):
            assignments.add(data['assignment'])
        if block.get('type') == 'upload':
            quizzes.update(q['quiz'] for q in data.get('quizzes', []) if isinstance(q, dict) and q.get('quiz'))
    for kind, value in re.findall(r'\{\{\s*(Quiz|Assignment)\("([^"]+)"\)', lesson.body or ''):
        (quizzes if kind == 'Quiz' else assignments).add(value)
    return quizzes, assignments

def lesson_eligible(lesson_name, member, assignment=None):
    lesson = frappe.get_doc('Course Lesson', lesson_name)
    quizzes, assignments = assessment_ids(lesson)
    for quiz in quizzes:
        if not frappe.db.count('LMS Quiz Question', {'parent': quiz}):
            return False
        threshold = frappe.db.get_value('LMS Quiz', quiz, 'passing_percentage')
        if threshold is None or not frappe.db.exists('LMS Quiz Submission', {'quiz': quiz, 'member': member, 'percentage': ['>=', threshold]}):
            return False
    if any(not frappe.db.exists('LMS Assignment Submission', {'assignment': a, 'member': member, 'status': 'Pass'}) for a in assignments):
        return False
    activities = bindings(lesson)
    if activities:
        candidates = [assignment] if assignment else [frappe.get_doc('BPO Training Assignment', name) for name in frappe.get_all(
            'BPO Training Assignment', filters={'course': lesson.course, 'member': member}, pluck='name')]
        for activity in activities:
            satisfied = False
            for a in candidates:
                if not a or a.member != member:
                    continue
                pinned = next((b for b in load_json(a.bindings_json, []) if b == activity), None)
                if not pinned:
                    continue
                attempts = frappe.get_all('AI Attempt', filters={'assignment': a.name, 'lesson': lesson_name,
                    'activity_id': activity['activity'], 'scenario_version': activity['version'], 'member': member},
                    fields=['channel', 'mode', 'status'])
                if len(approved_channels(activity['channels'], attempts)) == len(set(activity['channels'])):
                    satisfied = True
                    break
            if not satisfied:
                return False
    return True

def course_eligible(course, member, assignment=None):
    lessons = course_lessons(course)
    return bool(lessons) and all(lesson_eligible(l, member, assignment) and frappe.db.exists(
        'LMS Course Progress', {'lesson': l, 'member': member, 'status': 'Complete'}) for l in lessons)

def assignment_complete(a):
    if a.course:
        return course_eligible(a.course, a.member, a)
    channels = load_json(a.channels_json, [])
    attempts = frappe.get_all('AI Attempt', filters={'assignment': a.name, 'member': a.member}, fields=['channel', 'mode', 'status'])
    return bool(channels) and len(approved_channels(channels, attempts)) == len(channels)

def validate_progress(doc, method=None):
    if doc.status == 'Complete' and not lesson_eligible(doc.lesson, doc.member):
        frappe.throw('Complete and pass the required work and obtain AI Coach approvals first.')

def validate_certificate(doc, method=None):
    if doc.course and not course_eligible(doc.course, doc.member):
        frappe.throw('Required course work or approvals are incomplete.')
    if doc.batch_name:
        required = frappe.get_all('BPO Training Assignment', filters={'member': doc.member, 'batch': doc.batch_name, 'mandatory': 1}, pluck='name')
        if not required or any(not assignment_complete(frappe.get_doc('BPO Training Assignment', a)) for a in required):
            frappe.throw('Required batch assignments are incomplete.')
    if doc.published:
        frappe.throw('BPO certificates are private; public publication is disabled.')

def advance_after_review(attempt):
    if not attempt.lesson or not lesson_eligible(attempt.lesson, attempt.member):
        return
    from lms.lms.doctype.course_lesson.course_lesson import save_progress
    current = frappe.session.user
    try:
        frappe.set_user(attempt.member)
        save_progress(attempt.lesson)
    finally:
        frappe.set_user(current)
