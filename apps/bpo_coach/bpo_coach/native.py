"""Scope native course reads that intentionally bypass Frappe list permissions."""
from copy import deepcopy

import frappe

from bpo_coach.permissions import course_query, scope_course
from bpo_coach.security import is_admin, require_user


def course_filters(filters=None):
    require_user()
    filters = frappe.parse_json(filters) if isinstance(filters, str) else deepcopy(filters or {})
    if not isinstance(filters, dict):
        frappe.throw('Course filters must be an object.')
    if is_admin():
        return filters
    # Add the scope before upstream applies ordering and pagination. Filtering
    # its response afterwards would produce incorrect pages and total counts.
    allowed = {row[0] for row in frappe.db.sql(
        'SELECT name FROM `tabLMS Course` WHERE ' + course_query())}
    if 'name' in filters:
        allowed.intersection_update(frappe.get_all('LMS Course',
                                   filters={'name': filters.pop('name')}, pluck='name'))
    # Native LMS translates these virtual filters into a name condition. Resolve
    # them here so that translation cannot replace the process restriction.
    for virtual, doctype, field in [('enrolled', 'LMS Enrollment', 'member'),
                                     ('created', 'Course Instructor', 'instructor')]:
        if filters.pop(virtual, None):
            constraints = {field: frappe.session.user}
            if virtual == 'created':
                constraints['parenttype'] = 'LMS Course'
            allowed.intersection_update(frappe.get_all(doctype, filters=constraints,
                                       pluck='course' if virtual == 'enrolled' else 'parent'))
    filters['name'] = ['in', sorted(allowed)]
    return filters


def catalog_filters(filters):
    from lms.lms import utils
    requested = frappe.parse_json(filters) if isinstance(filters, str) else deepcopy(filters or {})
    if not isinstance(requested, dict):
        frappe.throw('Course filters must be an object.')
    self_scoped = utils.is_self_scoped(requested)
    scoped, or_filters, featured = utils.update_course_filters(course_filters(requested))
    utils.restrict_to_published(scoped, self_scoped)
    return scoped, or_filters, featured


@frappe.whitelist()
def get_courses(filters=None, start=0, limit_page_length=None):
    from lms.lms import utils
    from frappe.utils import cint
    filters, or_filters, show_featured = catalog_filters(filters)
    fields = utils.get_course_fields()
    page_length = utils.resolve_page_length(limit_page_length)
    start = max(cint(start), 0)
    featured = (utils.get_featured_courses(filters.copy(), or_filters, fields, start + page_length)
                if show_featured else [])
    courses = featured[start:start + page_length]
    remaining = page_length - len(courses)
    if remaining > 0:
        courses += frappe.get_all('LMS Course', filters=filters, fields=fields,
                                  or_filters=or_filters, order_by='enrollments desc',
                                  start=max(start - len(featured), 0), page_length=remaining)
    return utils.get_course_card_details(utils.get_enrollment_details(courses))


@frappe.whitelist()
def get_course_count(filters=None):
    from lms.lms import utils
    filters, or_filters, show_featured = catalog_filters(filters)
    total = utils.count_matching('LMS Course', filters, or_filters)
    if show_featured:
        total += utils.count_matching('LMS Course', {**filters, 'featured': 1}, or_filters)
    return total


@frappe.whitelist()
def get_course_details(course: str):
    require_user()
    from lms.lms.utils import get_course_details as original
    return original(course) if scope_course(course) else {}


@frappe.whitelist()
def get_course_outline(course: str, progress=False):
    require_user()
    from lms.lms.utils import get_course_outline as original
    return original(course, progress) if scope_course(course) else []


@frappe.whitelist()
def get_lesson(course: str, chapter: int, lesson: int):
    require_user()
    if not scope_course(course):
        frappe.throw('Course access denied.', frappe.PermissionError)
    from lms.lms.utils import get_lesson as original
    return original(course, chapter, lesson)


@frappe.whitelist()
def get_course_categories():
    from lms.lms.utils import get_course_categories as original
    if is_admin():
        return original()
    filters = course_filters()
    filters.update(published=1, category=['is', 'set'])
    categories = frappe.get_all('LMS Course', filters=filters, pluck='category',
                                distinct=True, order_by='category asc', limit_page_length=0)
    return [{'label': '', 'value': None}] + [{'label': value, 'value': value} for value in categories]
