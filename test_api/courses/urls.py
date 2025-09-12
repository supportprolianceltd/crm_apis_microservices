from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (AssignmentViewSet, AssignmentSubmissionViewSet,
    FAQStatsView, BadgeViewSet, UserBadgeViewSet, UserPointsViewSet, FAQViewSet,
    CategoryViewSet, CourseViewSet, ModuleViewSet, LessonViewSet, ResourceViewSet,
    EnrollmentViewSet, LearningPathViewSet, CertificateView, CertificateTemplateView,
    SCORMxAPIViewSet, SCORMTrackingView, SCORMCourseCreateView, serve_scorm_file, export_course_as_scorm
)

router = DefaultRouter()

router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'courses', CourseViewSet, basename='courses')
router.register(r'learning-paths', LearningPathViewSet, basename='learning-paths')
router.register(r'courses/(?P<course_id>\d+)/resources', ResourceViewSet, basename='resource')
router.register(r'badges', BadgeViewSet, basename='badges')
router.register(r'user-points', UserPointsViewSet, basename='user-points')
router.register(r'user-badges', UserBadgeViewSet, basename='user-badges')
router.register(r'enrollments/for/user', EnrollmentViewSet, basename='enrollment')
router.register(r'assignments', AssignmentViewSet, basename='assignment')
router.register(r'assignment-submissions', AssignmentSubmissionViewSet, basename='assignment-submission')

urlpatterns = [
    path('', include(router.urls)),
    
    path('courses/<int:course_id>/faqs/<int:pk>/', FAQViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='faq-detail'),
    path('courses/<int:course_id>/faqs/reorder/', FAQViewSet.as_view({'post': 'reorder'}), name='faq-reorder'),
    path('courses/<int:course_id>/resources/reorder/', ResourceViewSet.as_view({'post': 'reorder'}), name='resource-reorder'),
    path('courses/most_popular/', CourseViewSet.as_view({'get': 'most_popular'}), name='course-most-popular'),
    path('courses/least_popular/', CourseViewSet.as_view({'get': 'least_popular'}), name='course-least-popular'),
    path('courses/<int:course_id>/modules/', ModuleViewSet.as_view({'get': 'list', 'post': 'create'}), name='module-list'),
    path('courses/<int:course_id>/modules/<int:pk>/', ModuleViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='module-detail'),
    path('courses/<int:course_id>/modules/<int:module_id>/lessons/', LessonViewSet.as_view({'get': 'list', 'post': 'create'}), name='lesson-list'),
    path('courses/<int:course_id>/modules/<int:module_id>/lessons/<int:pk>/', LessonViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='lesson-detail'),
    
    # In courses/urls.py
    path('certificates/', CertificateView.as_view(), name='certificates'),
    path('certificates/course/<int:course_id>/', CertificateView.as_view(), name='certificate-course'),
    path('certificates/course/<int:course_id>/template/', CertificateTemplateView.as_view(), name='certificate-template'),

    path('enrollments/course/<int:course_id>/', EnrollmentViewSet.as_view({'get': 'list'}), name='course-enrollments'),
    path('enrollments/course/<int:course_id>/enroll/', EnrollmentViewSet.as_view({'post': 'enroll_to_course'}), name='enroll-to-course'),
    path('enrollments/course/<int:course_id>/bulk/', EnrollmentViewSet.as_view({'post': 'bulk_enroll'}), name='bulk-enroll'),
    path('enrollments/user/<int:user_id>/', EnrollmentViewSet.as_view({'get': 'user_enrollments'}), name='user-enrollments'),
    path('enrollments/all/', EnrollmentViewSet.as_view({'get': 'all_enrollments'}), name='all-enrollments'),
    path('enrollments/my-courses/', EnrollmentViewSet.as_view({'get': 'my_courses'}), name='my-courses'),

    path('courses/<int:pk>/scorm/upload/', SCORMxAPIViewSet.as_view({'post': 'upload'})),
    path('courses/<int:pk>/scorm/launch/', SCORMxAPIViewSet.as_view({'get': 'launch'})),
    path('courses/<int:pk>/scorm/player/', SCORMxAPIViewSet.as_view({'get': 'player'})),
    path('courses/<int:course_id>/scorm/track/', SCORMTrackingView.as_view()),
    path('scorm/create/', SCORMCourseCreateView.as_view(), name='scorm-create'),
    path('courses/<int:course_id>/scorm/export/', export_course_as_scorm, name='export_course_as_scorm'),

    path('media/scorm/<path:path>', serve_scorm_file, name='serve_scorm_file'),
]


