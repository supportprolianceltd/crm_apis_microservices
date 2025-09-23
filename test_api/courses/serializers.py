from rest_framework import serializers
from .models import (
    Category, Course, Module, Lesson, Resource, Instructor, CourseInstructor,
    CertificateTemplate, SCORMxAPISettings, LearningPath, Enrollment, Certificate,
    CourseRating, Badge, UserPoints, UserBadge, FAQ, Assignment, AssignmentSubmission
)
import logging
from django.utils.text import slugify
import uuid
from utils.storage import get_storage_service
import requests
from django.conf import settings
from activitylog.models import ActivityLog
import json
logger = logging.getLogger('courses')

def validate_user_id(user_id, tenant_id):
    """Validate user_id against auth-service."""
    try:
        response = requests.get(
            f"{settings.AUTH_SERVICE_URL}/api/user/users/{user_id}/",
            headers={"X-Tenant-ID": tenant_id},
            timeout=5
        )
        if response.status_code != 200:
            raise serializers.ValidationError(f"User with ID {user_id} does not exist.")
        return user_id
    except requests.RequestException as e:
        logger.error(f"Failed to validate user_id {user_id} for tenant {tenant_id}: {str(e)}")
        raise serializers.ValidationError("Unable to validate user ID.")

def validate_tenant_id(tenant_id):
    """Validate tenant_id against auth-service."""
    try:
        response = requests.get(
            f"{settings.AUTH_SERVICE_URL}/api/tenant/tenants/{tenant_id}/",
            timeout=5
        )
        if response.status_code != 200:
            raise serializers.ValidationError(f"Tenant with ID {tenant_id} does not exist.")
        return response.json().get('name', '')
    except requests.RequestException as e:
        logger.error(f"Failed to validate tenant_id {tenant_id}: {str(e)}")
        raise serializers.ValidationError("Unable to validate tenant ID.")

class FAQSerializer(serializers.ModelSerializer):
    tenant_id = serializers.CharField(write_only=True)
    tenant_name = serializers.CharField(read_only=True)

    class Meta:
        model = FAQ
        fields = ['id', 'tenant_id', 'tenant_name', 'course', 'question', 'answer', 'order', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'tenant_name']

    def validate(self, attrs):
        attrs['tenant_name'] = validate_tenant_id(attrs['tenant_id'])
        return attrs

    def create(self, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        instance = super().create(validated_data)
        ActivityLog.objects.create(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            user_id=None,
            activity_type='faq_created',
            details=f"FAQ for course {instance.course.title} created",
            status='success'
        )
        return instance

    def update(self, instance, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        instance = super().update(instance, validated_data)
        ActivityLog.objects.create(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            user_id=None,
            activity_type='faq_updated',
            details=f"FAQ for course {instance.course.title} updated",
            status='success'
        )
        return instance

class CategorySerializer(serializers.ModelSerializer):
    tenant_id = serializers.CharField(write_only=True)
    tenant_name = serializers.CharField(read_only=True)
    created_by_id = serializers.CharField(write_only=True)
    created_by_name = serializers.CharField(read_only=True)
    course_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'tenant_id', 'tenant_name', 'name', 'slug', 'description', 'created_by_id', 'created_by_name', 'course_count']
        read_only_fields = ['slug', 'created_by_name', 'course_count', 'tenant_name']

    def validate(self, attrs):
        attrs['tenant_name'] = validate_tenant_id(attrs['tenant_id'])
        validate_user_id(attrs['created_by_id'], attrs['tenant_id'])
        return attrs

    def create(self, validated_data):
        tenant_id = validated_data.get('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        created_by_id = validated_data.get('created_by_id')
        validated_data['slug'] = slugify(validated_data['name'])
        instance = super().create(validated_data)
        ActivityLog.objects.create(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            user_id=created_by_id,
            activity_type='category_created',
            details=f"Category {instance.name} created",
            status='success'
        )
        return instance

    def update(self, instance, validated_data):
        tenant_id = validated_data.get('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        created_by_id = validated_data.get('created_by_id')
        if 'name' in validated_data:
            validated_data['slug'] = slugify(validated_data['name'])
        instance = super().update(instance, validated_data)
        ActivityLog.objects.create(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            user_id=created_by_id,
            activity_type='category_updated',
            details=f"Category {instance.name} updated",
            status='success'
        )
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.created_by_id:
            try:
                response = requests.get(
                    f"{settings.AUTH_SERVICE_URL}/api/user/users/{instance.created_by_id}/",
                    headers={"X-Tenant-ID": instance.tenant_id},
                    timeout=5
                )
                if response.status_code == 200:
                    user_data = response.json()
                    representation['created_by_name'] = user_data.get('username', '')
            except requests.RequestException as e:
                logger.error(f"Failed to fetch created_by_name for user {instance.created_by_id}: {str(e)}")
                representation['created_by_name'] = ''
        return representation

class LessonSerializer(serializers.ModelSerializer):
    tenant_id = serializers.CharField(write_only=True)
    tenant_name = serializers.CharField(read_only=True)
    content_file_url = serializers.CharField(read_only=True)

    class Meta:
        model = Lesson
        fields = [
            'id', 'tenant_id', 'tenant_name', 'module', 'title', 'description', 'lesson_type',
            'duration', 'content_url', 'content_file', 'content_file_url', 'content_text',
            'order', 'is_published'
        ]
        read_only_fields = ['id', 'tenant_name', 'content_file_url']

    def validate(self, attrs):
        attrs['tenant_name'] = validate_tenant_id(attrs['tenant_id'])
        lesson_type = attrs.get('lesson_type', self.instance.lesson_type if self.instance else None)
        module = attrs.get('module', self.instance.module if self.instance else None)
        order = attrs.get('order', None)

        logger.debug(f"Validating lesson: lesson_type={lesson_type}, module={module}, order={order}")

        if order is not None and module:
            qs = Lesson.objects.filter(module=module, order=order)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(f"A lesson with order {order} already exists in this module.")
        
        if lesson_type == 'link' and not attrs.get('content_url'):
            raise serializers.ValidationError("Content URL is required for link lessons")
        if lesson_type in ['video', 'file'] and not attrs.get('content_file') and not (self.instance and self.instance.content_file):
            raise serializers.ValidationError("Content file is required for this lesson type")
        if lesson_type == 'text' and not attrs.get('content_text'):
            raise serializers.ValidationError("Content text is required for text lessons")
        return attrs

    def create(self, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        content_file = validated_data.pop('content_file', None)
        instance = super().create(validated_data)
        if content_file:
            file_name = f"courses/{instance.module.course.tenant_id}/{instance.module.course.slug}/lessons/{uuid.uuid4().hex}_{content_file.name}"
            try:
                storage_service = get_storage_service()
                storage_service.upload_file(content_file, file_name, content_type=content_file.content_type)
                instance.content_file = file_name
                instance.content_file_url = storage_service.get_public_url(file_name)
                instance.save()
                ActivityLog.objects.create(
                    tenant_id=tenant_id,
                    tenant_name=tenant_name,
                    user_id=None,
                    activity_type='lesson_created',
                    details=f"Lesson {instance.title} for module {instance.module.title} created",
                    status='success'
                )
            except Exception as e:
                logger.error(f"[Tenant {tenant_id}] Failed to upload content file: {str(e)}")
                raise serializers.ValidationError("Failed to upload content file")
        return instance

    def update(self, instance, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        content_file = validated_data.pop('content_file', None)
        instance = super().update(instance, validated_data)
        if content_file:
            storage_service = get_storage_service()
            if instance.content_file:
                storage_service.delete_file(instance.content_file)
            file_name = f"courses/{instance.module.course.tenant_id}/{instance.module.course.slug}/lessons/{uuid.uuid4().hex}_{content_file.name}"
            try:
                storage_service.upload_file(content_file, file_name, content_type=content_file.content_type)
                instance.content_file = file_name
                instance.content_file_url = storage_service.get_public_url(file_name)
                instance.save()
                ActivityLog.objects.create(
                    tenant_id=tenant_id,
                    tenant_name=tenant_name,
                    user_id=None,
                    activity_type='lesson_updated',
                    details=f"Lesson {instance.title} for module {instance.module.title} updated",
                    status='success'
                )
            except Exception as e:
                logger.error(f"[Tenant {tenant_id}] Failed to upload content file: {str(e)}")
                raise serializers.ValidationError("Failed to upload content file")
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['content_file_url'] = instance.content_file_url or ''
        return representation

class ModuleSerializer(serializers.ModelSerializer):
    tenant_id = serializers.CharField(write_only=True)
    tenant_name = serializers.CharField(read_only=True)
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ['id', 'tenant_id', 'tenant_name', 'title', 'course', 'description', 'order', 'is_published', 'lessons']
        read_only_fields = ['tenant_name']

    def validate(self, attrs):
        attrs['tenant_name'] = validate_tenant_id(attrs['tenant_id'])
        return attrs

    def create(self, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        instance = super().create(validated_data)
        ActivityLog.objects.create(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            user_id=None,
            activity_type='module_created',
            details=f"Module {instance.title} for course {instance.course.title} created",
            status='success'
        )
        return instance

    def update(self, instance, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        instance = super().update(instance, validated_data)
        ActivityLog.objects.create(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            user_id=None,
            activity_type='module_updated',
            details=f"Module {instance.title} for course {instance.course.title} updated",
            status='success'
        )
        return instance

class ResourceSerializer(serializers.ModelSerializer):
    tenant_id = serializers.CharField(write_only=True)
    tenant_name = serializers.CharField(read_only=True)
    file_url = serializers.CharField(read_only=True)

    class Meta:
        model = Resource
        fields = ['id', 'tenant_id', 'tenant_name', 'title', 'resource_type', 'url', 'file', 'file_url', 'order']
        read_only_fields = ['tenant_name', 'file_url']

    def validate(self, attrs):
        attrs['tenant_name'] = validate_tenant_id(attrs['tenant_id'])
        return attrs

    def create(self, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        file_obj = validated_data.pop('file', None)
        instance = super().create(validated_data)
        if file_obj:
            file_name = f"courses/{instance.course.tenant_id}/{instance.course.slug}/resources/{uuid.uuid4().hex}_{file_obj.name}"
            try:
                storage_service = get_storage_service()
                storage_service.upload_file(file_obj, file_name, content_type=file_obj.content_type)
                instance.file = file_name
                instance.file_url = storage_service.get_public_url(file_name)
                instance.save()
                ActivityLog.objects.create(
                    tenant_id=tenant_id,
                    tenant_name=tenant_name,
                    user_id=None,
                    activity_type='resource_created',
                    details=f"Resource {instance.title} for course {instance.course.title} created",
                    status='success'
                )
            except Exception as e:
                logger.error(f"[Tenant {tenant_id}] Failed to upload resource file: {str(e)}")
                raise serializers.ValidationError("Failed to upload resource file")
        return instance

    def update(self, instance, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        file_obj = validated_data.pop('file', None)
        instance = super().update(instance, validated_data)
        if file_obj:
            storage_service = get_storage_service()
            if instance.file:
                storage_service.delete_file(instance.file)
            file_name = f"courses/{instance.course.tenant_id}/{instance.course.slug}/resources/{uuid.uuid4().hex}_{file_obj.name}"
            try:
                storage_service.upload_file(file_obj, file_name, content_type=file_obj.content_type)
                instance.file = file_name
                instance.file_url = storage_service.get_public_url(file_name)
                instance.save()
                ActivityLog.objects.create(
                    tenant_id=tenant_id,
                    tenant_name=tenant_name,
                    user_id=None,
                    activity_type='resource_updated',
                    details=f"Resource {instance.title} for course {instance.course.title} updated",
                    status='success'
                )
            except Exception as e:
                logger.error(f"[Tenant {tenant_id}] Failed to upload resource file: {str(e)}")
                raise serializers.ValidationError("Failed to upload resource file")
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['file_url'] = instance.file_url or ''
        return representation

class InstructorUserSerializer(serializers.Serializer):
    id = serializers.CharField()
    email = serializers.CharField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    avatar_url = serializers.CharField(read_only=True)
    phone = serializers.CharField(read_only=True)

    def to_representation(self, instance):
        try:
            response = requests.get(
                f"{settings.AUTH_SERVICE_URL}/api/user/users/{instance}/",
                headers={"X-Tenant-ID": self.context['tenant_id']},
                timeout=5
            )
            if response.status_code == 200:
                user_data = response.json()
                return {
                    'id': instance,
                    'email': user_data.get('email', ''),
                    'first_name': user_data.get('first_name', ''),
                    'last_name': user_data.get('last_name', ''),
                    'avatar_url': user_data.get('profile', {}).get('avatar_url', ''),
                    'phone': user_data.get('profile', {}).get('phone', '')
                }
            else:
                logger.error(f"Failed to fetch user data for instructor {instance}: {response.status_code}")
                return {'id': instance, 'error': 'User data not found'}
        except requests.RequestException as e:
            logger.error(f"Failed to fetch user data for instructor {instance}: {str(e)}")
            return {'id': instance, 'error': 'Unable to fetch user data'}

class CertificateTemplateSerializer(serializers.ModelSerializer):
    tenant_id = serializers.CharField(write_only=True)
    tenant_name = serializers.CharField(read_only=True)
    logo_url = serializers.CharField(read_only=True)
    signature_url = serializers.CharField(read_only=True)

    class Meta:
        model = CertificateTemplate
        fields = [
            'id', 'tenant_id', 'tenant_name', 'course', 'is_active', 'template', 'custom_text',
            'logo', 'logo_url', 'signature', 'signature_url', 'signature_name', 'show_date',
            'show_course_name', 'show_completion_hours', 'min_score', 'require_all_modules'
        ]
        read_only_fields = ['tenant_name', 'logo_url', 'signature_url']

    def validate(self, attrs):
        attrs['tenant_name'] = validate_tenant_id(attrs['tenant_id'])
        return attrs

    def create(self, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        logo_file = validated_data.pop('logo', None)
        signature_file = validated_data.pop('signature', None)
        instance = super().create(validated_data)
        storage_service = get_storage_service()
        if logo_file:
            file_name = f"courses/{instance.course.tenant_id}/{instance.course.id}/certificates/logos/{uuid.uuid4().hex}_{logo_file.name}"
            try:
                storage_service.upload_file(logo_file, file_name, content_type=logo_file.content_type)
                instance.logo = file_name
                instance.logo_url = storage_service.get_public_url(file_name)
            except Exception as e:
                logger.error(f"[Tenant {tenant_id}] Failed to upload logo: {str(e)}")
                raise serializers.ValidationError("Failed to upload logo")
        if signature_file:
            file_name = f"courses/{instance.course.tenant_id}/{instance.course.id}/certificates/signatures/{uuid.uuid4().hex}_{signature_file.name}"
            try:
                storage_service.upload_file(signature_file, file_name, content_type=signature_file.content_type)
                instance.signature = file_name
                instance.signature_url = storage_service.get_public_url(file_name)
            except Exception as e:
                logger.error(f"[Tenant {tenant_id}] Failed to upload signature: {str(e)}")
                raise serializers.ValidationError("Failed to upload signature")
        if logo_file or signature_file:
            instance.save()
            ActivityLog.objects.create(
                tenant_id=tenant_id,
                tenant_name=tenant_name,
                user_id=None,
                activity_type='certificatetemplate_created',
                details=f"CertificateTemplate for course {instance.course.title} created",
                status='success'
            )
        return instance

    def update(self, instance, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        logo_file = validated_data.pop('logo', None)
        signature_file = validated_data.pop('signature', None)
        instance = super().update(instance, validated_data)
        storage_service = get_storage_service()
        if logo_file:
            if instance.logo:
                storage_service.delete_file(instance.logo)
            file_name = f"courses/{instance.course.tenant_id}/{instance.course.id}/certificates/logos/{uuid.uuid4().hex}_{logo_file.name}"
            try:
                storage_service.upload_file(logo_file, file_name, content_type=logo_file.content_type)
                instance.logo = file_name
                instance.logo_url = storage_service.get_public_url(file_name)
            except Exception as e:
                logger.error(f"[Tenant {tenant_id}] Failed to upload logo: {str(e)}")
                raise serializers.ValidationError("Failed to upload logo")
        if signature_file:
            if instance.signature:
                storage_service.delete_file(instance.signature)
            file_name = f"courses/{instance.course.tenant_id}/{instance.course.id}/certificates/signatures/{uuid.uuid4().hex}_{signature_file.name}"
            try:
                storage_service.upload_file(signature_file, file_name, content_type=signature_file.content_type)
                instance.signature = file_name
                instance.signature_url = storage_service.get_public_url(file_name)
            except Exception as e:
                logger.error(f"[Tenant {tenant_id}] Failed to upload signature: {str(e)}")
                raise serializers.ValidationError("Failed to upload signature")
        if logo_file or signature_file:
            instance.save()
            ActivityLog.objects.create(
                tenant_id=tenant_id,
                tenant_name=tenant_name,
                user_id=None,
                activity_type='certificatetemplate_updated',
                details=f"CertificateTemplate for course {instance.course.title} updated",
                status='success'
            )
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['logo_url'] = instance.logo_url or ''
        representation['signature_url'] = instance.signature_url or ''
        return representation

class SCORMxAPISettingsSerializer(serializers.ModelSerializer):
    tenant_id = serializers.CharField(write_only=True)
    tenant_name = serializers.CharField(read_only=True)
    package_url = serializers.CharField(read_only=True)

    class Meta:
        model = SCORMxAPISettings
        fields = [
            'id', 'tenant_id', 'tenant_name', 'course', 'is_active', 'standard', 'version',
            'completion_threshold', 'score_threshold', 'track_completion', 'track_score',
            'track_time', 'track_progress', 'package', 'package_url'
        ]
        read_only_fields = ['tenant_name', 'package_url']

    def validate(self, attrs):
        attrs['tenant_name'] = validate_tenant_id(attrs['tenant_id'])
        return attrs

    def create(self, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        package_file = validated_data.pop('package', None)
        instance = super().create(validated_data)
        if package_file:
            file_name = f"courses/{instance.course.tenant_id}/{instance.course.slug}/scorm_packages/{uuid.uuid4().hex}_{package_file.name}"
            try:
                storage_service = get_storage_service()
                storage_service.upload_file(package_file, file_name, content_type=package_file.content_type)
                instance.package = file_name
                instance.package_url = storage_service.get_public_url(file_name)
                instance.save()
                ActivityLog.objects.create(
                    tenant_id=tenant_id,
                    tenant_name=tenant_name,
                    user_id=None,
                    activity_type='scormsettings_created',
                    details=f"SCORMxAPISettings for course {instance.course.title} created",
                    status='success'
                )
            except Exception as e:
                logger.error(f"[Tenant {tenant_id}] Failed to upload SCORM package: {str(e)}")
                raise serializers.ValidationError("Failed to upload SCORM package")
        return instance

    def update(self, instance, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        package_file = validated_data.pop('package', None)
        instance = super().update(instance, validated_data)
        if package_file:
            storage_service = get_storage_service()
            if instance.package:
                storage_service.delete_file(instance.package)
            file_name = f"courses/{instance.course.tenant_id}/{instance.course.slug}/scorm_packages/{uuid.uuid4().hex}_{package_file.name}"
            try:
                storage_service.upload_file(package_file, file_name, content_type=package_file.content_type)
                instance.package = file_name
                instance.package_url = storage_service.get_public_url(file_name)
                instance.save()
                ActivityLog.objects.create(
                    tenant_id=tenant_id,
                    tenant_name=tenant_name,
                    user_id=None,
                    activity_type='scormsettings_updated',
                    details=f"SCORMxAPISettings for course {instance.course.title} updated",
                    status='success'
                )
            except Exception as e:
                logger.error(f"[Tenant {tenant_id}] Failed to upload SCORM package: {str(e)}")
                raise serializers.ValidationError("Failed to upload SCORM package")
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['package_url'] = instance.package_url or ''
        return representation

class CourseSerializer(serializers.ModelSerializer):
    tenant_id = serializers.CharField(write_only=True)
    tenant_name = serializers.CharField(read_only=True)
    created_by_id = serializers.CharField(write_only=True)
    created_by_name = serializers.CharField(read_only=True)
    thumbnail_url = serializers.CharField(read_only=True)
    scorm_settings = SCORMxAPISettingsSerializer(read_only=True)
    course_instructors = serializers.SerializerMethodField()
    faq_count = serializers.IntegerField(read_only=True)
    faqs = FAQSerializer(many=True, read_only=True)
    total_enrollments = serializers.IntegerField(read_only=True)
    resources = ResourceSerializer(many=True, read_only=True)
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), source='category', write_only=True)
    learning_outcomes = serializers.ListField(
        child=serializers.CharField(max_length=500, allow_blank=True),
        required=False,
        default=list
    )
    prerequisites = serializers.ListField(
        child=serializers.CharField(max_length=500, allow_blank=True),
        required=False,
        default=list
    )
    modules = ModuleSerializer(many=True, read_only=True)
    certificate_settings = CertificateTemplateSerializer(read_only=True)
    current_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Course
        fields = [
            'id', 'tenant_id', 'tenant_name', 'title', 'learning_outcomes', 'prerequisites', 'slug', 'code',
            'description', 'is_free', 'short_description', 'category', 'category_id', 'level', 'status',
            'duration', 'price', 'discount_price', 'currency', 'thumbnail', 'thumbnail_url', 'faq_count',
            'faqs', 'created_at', 'updated_at', 'created_by_id', 'created_by_name', 'completion_hours',
            'current_price', 'course_type', 'modules', 'resources', 'course_instructors', 'certificate_settings',
            'scorm_settings', 'scorm_launch_path', 'total_enrollments'
        ]
        read_only_fields = ['tenant_name', 'created_by_name', 'thumbnail_url', 'scorm_launch_path']

    def validate(self, attrs):
        attrs['tenant_name'] = validate_tenant_id(attrs['tenant_id'])
        validate_user_id(attrs['created_by_id'], attrs['tenant_id'])
        return attrs

    def get_course_instructors(self, obj):
        instructors = CourseInstructor.objects.filter(course=obj)
        return InstructorUserSerializer([ci.instructor_id for ci in instructors], many=True, context={'tenant_id': obj.tenant_id}).data

    def to_internal_value(self, data):
        for field in ['learning_outcomes', 'prerequisites']:
            if field in data:
                value = data[field]
                if isinstance(value, list):
                    cleaned_value = []
                    for item in value:
                        try:
                            parsed = item if isinstance(item, str) else json.loads(item)
                            cleaned_value.append(str(parsed) if not isinstance(parsed, str) else parsed)
                        except (json.JSONDecodeError, TypeError):
                            cleaned_value.append(str(item))
                    data[field] = cleaned_value
        return super().to_internal_value(data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['thumbnail_url'] = instance.thumbnail_url or ''
        if instance.created_by_id:
            try:
                response = requests.get(
                    f"{settings.AUTH_SERVICE_URL}/api/user/users/{instance.created_by_id}/",
                    headers={"X-Tenant-ID": instance.tenant_id},
                    timeout=5
                )
                if response.status_code == 200:
                    user_data = response.json()
                    representation['created_by_name'] = user_data.get('username', '')
            except requests.RequestException as e:
                logger.error(f"Failed to fetch created_by_name for user {instance.created_by_id}: {str(e)}")
                representation['created_by_name'] = ''
        if 'learning_outcomes' in representation:
            representation['learning_outcomes'] = self.flatten_array(representation['learning_outcomes'])
        if 'prerequisites' in representation:
            representation['prerequisites'] = self.flatten_array(representation['prerequisites'])
        return representation

    def flatten_array(self, data):
        flat_list = []
        for item in data:
            if isinstance(item, list):
                flat_list.extend([str(i) for i in item])
            elif isinstance(item, str):
                try:
                    parsed = json.loads(item)
                    if isinstance(parsed, list):
                        flat_list.extend([str(i) for i in parsed])
                    else:
                        flat_list.append(item)
                except json.JSONDecodeError:
                    flat_list.append(item)
            else:
                flat_list.append(str(item))
        return flat_list

    def create(self, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        created_by_id = validated_data.pop('created_by_id')
        thumbnail_file = validated_data.pop('thumbnail', None)
        if 'slug' not in validated_data or not validated_data['slug']:
            validated_data['slug'] = slugify(validated_data['title'])
        instance = super().create(validated_data)
        if thumbnail_file:
            file_name = f"courses/{instance.tenant_id}/{instance.slug}/thumbnails/{uuid.uuid4().hex}_{thumbnail_file.name}"
            try:
                storage_service = get_storage_service()
                storage_service.upload_file(thumbnail_file, file_name, content_type=thumbnail_file.content_type)
                instance.thumbnail = file_name
                instance.thumbnail_url = storage_service.get_public_url(file_name)
                instance.save()
                ActivityLog.objects.create(
                    tenant_id=tenant_id,
                    tenant_name=tenant_name,
                    user_id=created_by_id,
                    activity_type='course_created',
                    details=f"Course {instance.title} created",
                    status='success'
                )
            except Exception as e:
                logger.error(f"[Tenant {tenant_id}] Failed to upload thumbnail: {str(e)}")
                raise serializers.ValidationError("Failed to upload thumbnail")
        return instance

    def update(self, instance, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        created_by_id = validated_data.pop('created_by_id')
        thumbnail_file = validated_data.pop('thumbnail', None)
        if 'title' in validated_data:
            validated_data['slug'] = slugify(validated_data['title'])
        instance = super().update(instance, validated_data)
        if thumbnail_file:
            storage_service = get_storage_service()
            if instance.thumbnail:
                storage_service.delete_file(instance.thumbnail)
            file_name = f"courses/{instance.tenant_id}/{instance.slug}/thumbnails/{uuid.uuid4().hex}_{thumbnail_file.name}"
            try:
                storage_service.upload_file(thumbnail_file, file_name, content_type=thumbnail_file.content_type)
                instance.thumbnail = file_name
                instance.thumbnail_url = storage_service.get_public_url(file_name)
                instance.save()
                ActivityLog.objects.create(
                    tenant_id=tenant_id,
                    tenant_name=tenant_name,
                    user_id=created_by_id,
                    activity_type='course_updated',
                    details=f"Course {instance.title} updated",
                    status='success'
                )
            except Exception as e:
                logger.error(f"[Tenant {tenant_id}] Failed to upload thumbnail: {str(e)}")
                raise serializers.ValidationError("Failed to upload thumbnail")
        return instance

class LearningPathSerializer(serializers.ModelSerializer):
    tenant_id = serializers.CharField(write_only=True)
    tenant_name = serializers.CharField(read_only=True)
    created_by_id = serializers.CharField(write_only=True)
    created_by_name = serializers.CharField(read_only=True)
    courses = CourseSerializer(many=True, read_only=True)
    course_ids = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all(), many=True, source='courses', write_only=True)

    class Meta:
        model = LearningPath
        fields = [
            'id', 'tenant_id', 'tenant_name', 'title', 'description', 'courses', 'course_ids',
            'is_active', 'order', 'created_at', 'updated_at', 'created_by_id', 'created_by_name'
        ]
        read_only_fields = ['tenant_name', 'created_by_name']

    def validate(self, attrs):
        attrs['tenant_name'] = validate_tenant_id(attrs['tenant_id'])
        validate_user_id(attrs['created_by_id'], attrs['tenant_id'])
        return attrs

    def create(self, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        created_by_id = validated_data.pop('created_by_id')
        instance = super().create(validated_data)
        ActivityLog.objects.create(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            user_id=created_by_id,
            activity_type='learningpath_created',
            details=f"LearningPath {instance.title} created",
            status='success'
        )
        return instance

    def update(self, instance, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        created_by_id = validated_data.pop('created_by_id')
        instance = super().update(instance, validated_data)
        ActivityLog.objects.create(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            user_id=created_by_id,
            activity_type='learningpath_updated',
            details=f"LearningPath {instance.title} updated",
            status='success'
        )
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.created_by_id:
            try:
                response = requests.get(
                    f"{settings.AUTH_SERVICE_URL}/api/user/users/{instance.created_by_id}/",
                    headers={"X-Tenant-ID": instance.tenant_id},
                    timeout=5
                )
                if response.status_code == 200:
                    user_data = response.json()
                    representation['created_by_name'] = user_data.get('username', '')
            except requests.RequestException as e:
                logger.error(f"Failed to fetch created_by_name for user {instance.created_by_id}: {str(e)}")
                representation['created_by_name'] = ''
        return representation

class EnrollmentCourseSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Course
        fields = '__all__'

class EnrollmentSerializer(serializers.ModelSerializer):
    tenant_id = serializers.CharField(write_only=True)
    tenant_name = serializers.CharField(read_only=True)
    user_id = serializers.CharField(write_only=True)
    user_name = serializers.CharField(read_only=True)
    course = EnrollmentCourseSerializer(read_only=True)
    course_id = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all(), source='course', write_only=True)

    class Meta:
        model = Enrollment
        fields = [
            'id', 'tenant_id', 'tenant_name', 'user_id', 'user_name', 'course', 'course_id',
            'enrolled_at', 'started_at', 'completed_at', 'is_active'
        ]
        read_only_fields = ['tenant_name', 'user_name', 'enrolled_at']

    def validate(self, attrs):
        attrs['tenant_name'] = validate_tenant_id(attrs['tenant_id'])
        validate_user_id(attrs['user_id'], attrs['tenant_id'])
        return attrs

    def create(self, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        user_id = validated_data.pop('user_id')
        instance = super().create(validated_data)
        ActivityLog.objects.create(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            user_id=user_id,
            activity_type='enrollment_created',
            details=f"Enrollment for course {instance.course.title} created",
            status='success'
        )
        return instance

    def update(self, instance, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        user_id = validated_data.pop('user_id')
        instance = super().update(instance, validated_data)
        ActivityLog.objects.create(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            user_id=user_id,
            activity_type='enrollment_updated',
            details=f"Enrollment for course {instance.course.title} updated",
            status='success'
        )
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.user_id:
            try:
                response = requests.get(
                    f"{settings.AUTH_SERVICE_URL}/api/user/users/{instance.user_id}/",
                    headers={"X-Tenant-ID": instance.tenant_id},
                    timeout=5
                )
                if response.status_code == 200:
                    user_data = response.json()
                    representation['user_name'] = user_data.get('username', '')
            except requests.RequestException as e:
                logger.error(f"Failed to fetch user_name for user {instance.user_id}: {str(e)}")
                representation['user_name'] = ''
        return representation

class BulkEnrollmentSerializer(serializers.Serializer):
    tenant_id = serializers.CharField()
    tenant_name = serializers.CharField(read_only=True)
    user_id = serializers.CharField()
    user_name = serializers.CharField(read_only=True)
    course_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        attrs['tenant_name'] = validate_tenant_id(attrs['tenant_id'])
        validate_user_id(attrs['user_id'], attrs['tenant_id'])
        if 'course_id' in attrs and not Course.objects.filter(id=attrs['course_id'], status='Published').exists():
            raise serializers.ValidationError("Course does not exist or is not published")
        return attrs

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.get('user_id'):
            try:
                response = requests.get(
                    f"{settings.AUTH_SERVICE_URL}/api/user/users/{instance['user_id']}/",
                    headers={"X-Tenant-ID": instance['tenant_id']},
                    timeout=5
                )
                if response.status_code == 200:
                    user_data = response.json()
                    representation['user_name'] = user_data.get('username', '')
            except requests.RequestException as e:
                logger.error(f"Failed to fetch user_name for user {instance['user_id']}: {str(e)}")
                representation['user_name'] = ''
        return representation

class CertificateSerializer(serializers.ModelSerializer):
    tenant_id = serializers.CharField(write_only=True)
    tenant_name = serializers.CharField(read_only=True)
    pdf_file_url = serializers.CharField(read_only=True)
    course_title = serializers.CharField(source='enrollment.course.title', read_only=True)
    user_name = serializers.CharField(read_only=True)

    class Meta:
        model = Certificate
        fields = [
            'id', 'tenant_id', 'tenant_name', 'enrollment', 'course_title', 'user_name',
            'issued_at', 'certificate_id', 'pdf_file', 'pdf_file_url'
        ]
        read_only_fields = ['tenant_name', 'user_name', 'issued_at', 'certificate_id', 'pdf_file_url']

    def validate(self, attrs):
        attrs['tenant_name'] = validate_tenant_id(attrs['tenant_id'])
        return attrs

    def create(self, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        pdf_file = validated_data.pop('pdf_file', None)
        instance = super().create(validated_data)
        if pdf_file:
            file_name = f"certificates/pdfs/{instance.enrollment.tenant_id}/{uuid.uuid4().hex}_{pdf_file.name}"
            try:
                storage_service = get_storage_service()
                storage_service.upload_file(pdf_file, file_name, content_type=pdf_file.content_type)
                instance.pdf_file = file_name
                instance.pdf_file_url = storage_service.get_public_url(file_name)
                instance.save()
                ActivityLog.objects.create(
                    tenant_id=tenant_id,
                    tenant_name=tenant_name,
                    user_id=instance.enrollment.user_id,
                    activity_type='certificate_created',
                    details=f"Certificate {instance.certificate_id} for course {instance.enrollment.course.title} created",
                    status='success'
                )
            except Exception as e:
                logger.error(f"[Tenant {tenant_id}] Failed to upload PDF file: {str(e)}")
                raise serializers.ValidationError("Failed to upload PDF file")
        return instance

    def update(self, instance, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        pdf_file = validated_data.pop('pdf_file', None)
        instance = super().update(instance, validated_data)
        if pdf_file:
            storage_service = get_storage_service()
            if instance.pdf_file:
                storage_service.delete_file(instance.pdf_file)
            file_name = f"certificates/pdfs/{instance.enrollment.tenant_id}/{uuid.uuid4().hex}_{pdf_file.name}"
            try:
                storage_service.upload_file(pdf_file, file_name, content_type=pdf_file.content_type)
                instance.pdf_file = file_name
                instance.pdf_file_url = storage_service.get_public_url(file_name)
                instance.save()
                ActivityLog.objects.create(
                    tenant_id=tenant_id,
                    tenant_name=tenant_name,
                    user_id=instance.enrollment.user_id,
                    activity_type='certificate_updated',
                    details=f"Certificate {instance.certificate_id} for course {instance.enrollment.course.title} updated",
                    status='success'
                )
            except Exception as e:
                logger.error(f"[Tenant {tenant_id}] Failed to upload PDF file: {str(e)}")
                raise serializers.ValidationError("Failed to upload PDF file")
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['pdf_file_url'] = instance.pdf_file_url or ''
        if instance.enrollment.user_id:
            try:
                response = requests.get(
                    f"{settings.AUTH_SERVICE_URL}/api/user/users/{instance.enrollment.user_id}/",
                    headers={"X-Tenant-ID": instance.enrollment.tenant_id},
                    timeout=5
                )
                if response.status_code == 200:
                    user_data = response.json()
                    representation['user_name'] = user_data.get('username', '')
            except requests.RequestException as e:
                logger.error(f"Failed to fetch user_name for user {instance.enrollment.user_id}: {str(e)}")
                representation['user_name'] = ''
        return representation

class CourseRatingSerializer(serializers.ModelSerializer):
    tenant_id = serializers.CharField(write_only=True)
    tenant_name = serializers.CharField(read_only=True)
    user_id = serializers.CharField(write_only=True)
    user_name = serializers.CharField(read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = CourseRating
        fields = [
            'id', 'tenant_id', 'tenant_name', 'user_id', 'user_name', 'course', 'course_title',
            'rating', 'review', 'created_at', 'updated_at'
        ]
        read_only_fields = ['tenant_name', 'user_name', 'created_at', 'updated_at']

    def validate(self, attrs):
        attrs['tenant_name'] = validate_tenant_id(attrs['tenant_id'])
        validate_user_id(attrs['user_id'], attrs['tenant_id'])
        return attrs

    def create(self, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        user_id = validated_data.pop('user_id')
        instance = super().create(validated_data)
        ActivityLog.objects.create(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            user_id=user_id,
            activity_type='courserating_created',
            details=f"CourseRating for course {instance.course.title} created",
            status='success'
        )
        return instance

    def update(self, instance, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        user_id = validated_data.pop('user_id')
        instance = super().update(instance, validated_data)
        ActivityLog.objects.create(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            user_id=user_id,
            activity_type='courserating_updated',
            details=f"CourseRating for course {instance.course.title} updated",
            status='success'
        )
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.user_id:
            try:
                response = requests.get(
                    f"{settings.AUTH_SERVICE_URL}/api/user/users/{instance.user_id}/",
                    headers={"X-Tenant-ID": instance.tenant_id},
                    timeout=5
                )
                if response.status_code == 200:
                    user_data = response.json()
                    representation['user_name'] = user_data.get('username', '')
            except requests.RequestException as e:
                logger.error(f"Failed to fetch user_name for user {instance.user_id}: {str(e)}")
                representation['user_name'] = ''
        return representation

class BadgeSerializer(serializers.ModelSerializer):
    tenant_id = serializers.CharField(write_only=True)
    tenant_name = serializers.CharField(read_only=True)
    image_url = serializers.CharField(read_only=True)

    class Meta:
        model = Badge
        fields = [
            'id', 'tenant_id', 'tenant_name', 'title', 'description', 'image', 'image_url',
            'criteria', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['tenant_name', 'image_url', 'created_at', 'updated_at']

    def validate(self, attrs):
        attrs['tenant_name'] = validate_tenant_id(attrs['tenant_id'])
        return attrs

    def create(self, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        image_file = validated_data.pop('image', None)
        instance = super().create(validated_data)
        if image_file:
            file_name = f"badges/{instance.tenant_id}/{uuid.uuid4().hex}_{image_file.name}"
            try:
                storage_service = get_storage_service()
                storage_service.upload_file(image_file, file_name, content_type=image_file.content_type)
                instance.image = file_name
                instance.image_url = storage_service.get_public_url(file_name)
                instance.save()
                ActivityLog.objects.create(
                    tenant_id=tenant_id,
                    tenant_name=tenant_name,
                    user_id=None,
                    activity_type='badge_created',
                    details=f"Badge {instance.title} created",
                    status='success'
                )
            except Exception as e:
                logger.error(f"[Tenant {tenant_id}] Failed to upload badge image: {str(e)}")
                raise serializers.ValidationError("Failed to upload badge image")
        return instance

    def update(self, instance, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        image_file = validated_data.pop('image', None)
        instance = super().update(instance, validated_data)
        if image_file:
            storage_service = get_storage_service()
            if instance.image:
                storage_service.delete_file(instance.image)
            file_name = f"badges/{instance.tenant_id}/{uuid.uuid4().hex}_{image_file.name}"
            try:
                storage_service.upload_file(image_file, file_name, content_type=image_file.content_type)
                instance.image = file_name
                instance.image_url = storage_service.get_public_url(file_name)
                instance.save()
                ActivityLog.objects.create(
                    tenant_id=tenant_id,
                    tenant_name=tenant_name,
                    user_id=None,
                    activity_type='badge_updated',
                    details=f"Badge {instance.title} updated",
                    status='success'
                )
            except Exception as e:
                logger.error(f"[Tenant {tenant_id}] Failed to upload badge image: {str(e)}")
                raise serializers.ValidationError("Failed to upload badge image")
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['image_url'] = instance.image_url or ''
        return representation

class UserPointsSerializer(serializers.ModelSerializer):
    tenant_id = serializers.CharField(write_only=True)
    tenant_name = serializers.CharField(read_only=True)
    user_id = serializers.CharField(write_only=True)
    user_name = serializers.CharField(read_only=True)

    class Meta:
        model = UserPoints
        fields = [
            'id', 'tenant_id', 'tenant_name', 'user_id', 'user_name', 'course', 'points',
            'activity_type', 'created_at'
        ]
        read_only_fields = ['tenant_name', 'user_name', 'created_at']

    def validate(self, attrs):
        attrs['tenant_name'] = validate_tenant_id(attrs['tenant_id'])
        validate_user_id(attrs['user_id'], attrs['tenant_id'])
        return attrs

    def create(self, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        user_id = validated_data.pop('user_id')
        instance = super().create(validated_data)
        ActivityLog.objects.create(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            user_id=user_id,
            activity_type='userpoints_created',
            details=f"UserPoints for activity {instance.activity_type} created",
            status='success'
        )
        return instance

    def update(self, instance, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        user_id = validated_data.pop('user_id')
        instance = super().update(instance, validated_data)
        ActivityLog.objects.create(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            user_id=user_id,
            activity_type='userpoints_updated',
            details=f"UserPoints for activity {instance.activity_type} updated",
            status='success'
        )
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.user_id:
            try:
                response = requests.get(
                    f"{settings.AUTH_SERVICE_URL}/api/user/users/{instance.user_id}/",
                    headers={"X-Tenant-ID": instance.tenant_id},
                    timeout=5
                )
                if response.status_code == 200:
                    user_data = response.json()
                    representation['user_name'] = user_data.get('username', '')
            except requests.RequestException as e:
                logger.error(f"Failed to fetch user_name for user {instance.user_id}: {str(e)}")
                representation['user_name'] = ''
        return representation

class UserBadgeSerializer(serializers.ModelSerializer):
    tenant_id = serializers.CharField(write_only=True)
    tenant_name = serializers.CharField(read_only=True)
    user_id = serializers.CharField(write_only=True)
    user_name = serializers.CharField(read_only=True)
    badge = BadgeSerializer(read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True, allow_null=True)

    class Meta:
        model = UserBadge
        fields = [
            'id', 'tenant_id', 'tenant_name', 'user_id', 'user_name', 'badge', 'awarded_at', 'course', 'course_title'
        ]
        read_only_fields = ['tenant_name', 'user_name', 'awarded_at']

    def validate(self, attrs):
        attrs['tenant_name'] = validate_tenant_id(attrs['tenant_id'])
        validate_user_id(attrs['user_id'], attrs['tenant_id'])
        return attrs

    def create(self, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        user_id = validated_data.pop('user_id')
        instance = super().create(validated_data)
        ActivityLog.objects.create(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            user_id=user_id,
            activity_type='userbadge_created',
            details=f"UserBadge {instance.badge.title} for course {instance.course.title if instance.course else 'N/A'} created",
            status='success'
        )
        return instance

    def update(self, instance, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        user_id = validated_data.pop('user_id')
        instance = super().update(instance, validated_data)
        ActivityLog.objects.create(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            user_id=user_id,
            activity_type='userbadge_updated',
            details=f"UserBadge {instance.badge.title} for course {instance.course.title if instance.course else 'N/A'} updated",
            status='success'
        )
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.user_id:
            try:
                response = requests.get(
                    f"{settings.AUTH_SERVICE_URL}/api/user/users/{instance.user_id}/",
                    headers={"X-Tenant-ID": instance.tenant_id},
                    timeout=5
                )
                if response.status_code == 200:
                    user_data = response.json()
                    representation['user_name'] = user_data.get('username', '')
            except requests.RequestException as e:
                logger.error(f"Failed to fetch user_name for user {instance.user_id}: {str(e)}")
                representation['user_name'] = ''
        return representation

class AssignmentSerializer(serializers.ModelSerializer):
    tenant_id = serializers.CharField(write_only=True)
    tenant_name = serializers.CharField(read_only=True)
    created_by_id = serializers.CharField(write_only=True)
    created_by_name = serializers.CharField(read_only=True)
    course_name = serializers.CharField(source='course.title', read_only=True)
    module_name = serializers.CharField(source='module.title', read_only=True, allow_null=True)
    instructions_file_url = serializers.CharField(read_only=True)

    class Meta:
        model = Assignment
        fields = [
            'id', 'tenant_id', 'tenant_name', 'course', 'module', 'title', 'description',
            'instructions_file', 'instructions_file_url', 'due_date', 'created_by_id',
            'created_by_name', 'created_at', 'course_name', 'module_name'
        ]
        read_only_fields = ['tenant_name', 'created_by_name', 'created_at', 'course_name', 'module_name', 'instructions_file_url']

    def validate(self, attrs):
        attrs['tenant_name'] = validate_tenant_id(attrs['tenant_id'])
        validate_user_id(attrs['created_by_id'], attrs['tenant_id'])
        course = attrs.get('course', self.instance.course if self.instance else None)
        module = attrs.get('module', self.instance.module if self.instance else None)
        title = attrs.get('title', self.instance.title if self.instance else None)
        due_date = attrs.get('due_date', self.instance.due_date if self.instance else None)

        logger.debug(f"Validating assignment: course={course}, module={module}, title={title}, due_date={due_date}")

        if not course:
            raise serializers.ValidationError("Course is required for assignment.")
        if not title:
            raise serializers.ValidationError("Title is required for assignment.")
        if not due_date:
            raise serializers.ValidationError("Due date is required for assignment.")

        qs = Assignment.objects.filter(course=course, title=title)
        if module:
            qs = qs.filter(module=module)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("An assignment with this title already exists for this module/course.")
        
        return attrs

    def create(self, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        created_by_id = validated_data.pop('created_by_id')
        instructions_file = validated_data.pop('instructions_file', None)
        instance = super().create(validated_data)
        if instructions_file:
            file_name = f"courses/{instance.course.tenant_id}/{instance.course.slug}/assignments/{uuid.uuid4().hex}_{instructions_file.name}"
            try:
                storage_service = get_storage_service()
                storage_service.upload_file(instructions_file, file_name, content_type=instructions_file.content_type)
                instance.instructions_file = file_name
                instance.instructions_file_url = storage_service.get_public_url(file_name)
                instance.save()
                ActivityLog.objects.create(
                    tenant_id=tenant_id,
                    tenant_name=tenant_name,
                    user_id=created_by_id,
                    activity_type='assignment_created',
                    details=f"Assignment {instance.title} for course {instance.course.title} created",
                    status='success'
                )
            except Exception as e:
                logger.error(f"[Tenant {tenant_id}] Failed to upload assignment file: {str(e)}")
                raise serializers.ValidationError("Failed to upload assignment file")
        return instance

    def update(self, instance, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        created_by_id = validated_data.pop('created_by_id')
        instructions_file = validated_data.pop('instructions_file', None)
        instance = super().update(instance, validated_data)
        if instructions_file:
            storage_service = get_storage_service()
            if instance.instructions_file:
                storage_service.delete_file(instance.instructions_file)
            file_name = f"courses/{instance.course.tenant_id}/{instance.course.slug}/assignments/{uuid.uuid4().hex}_{instructions_file.name}"
            try:
                storage_service.upload_file(instructions_file, file_name, content_type=instructions_file.content_type)
                instance.instructions_file = file_name
                instance.instructions_file_url = storage_service.get_public_url(file_name)
                instance.save()
                ActivityLog.objects.create(
                    tenant_id=tenant_id,
                    tenant_name=tenant_name,
                    user_id=created_by_id,
                    activity_type='assignment_updated',
                    details=f"Assignment {instance.title} for course {instance.course.title} updated",
                    status='success'
                )
            except Exception as e:
                logger.error(f"[Tenant {tenant_id}] Failed to upload assignment file: {str(e)}")
                raise serializers.ValidationError("Failed to upload assignment file")
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['instructions_file_url'] = instance.instructions_file_url or ''
        if instance.created_by_id:
            try:
                response = requests.get(
                    f"{settings.AUTH_SERVICE_URL}/api/user/users/{instance.created_by_id}/",
                    headers={"X-Tenant-ID": instance.course.tenant_id},
                    timeout=5
                )
                if response.status_code == 200:
                    user_data = response.json()
                    representation['created_by_name'] = user_data.get('username', '')
            except requests.RequestException as e:
                logger.error(f"Failed to fetch created_by_name for user {instance.created_by_id}: {str(e)}")
                representation['created_by_name'] = ''
        return representation

class AssignmentBriefSerializer(serializers.ModelSerializer):
    tenant_id = serializers.CharField(write_only=True)
    tenant_name = serializers.CharField(read_only=True)
    course_name = serializers.CharField(source='course.title', read_only=True)
    module_name = serializers.CharField(source='module.title', read_only=True, allow_null=True)

    class Meta:
        model = Assignment
        fields = ['id', 'tenant_id', 'tenant_name', 'title', 'course_name', 'module_name']
        read_only_fields = ['tenant_name', 'course_name', 'module_name']

    def validate(self, attrs):
        attrs['tenant_name'] = validate_tenant_id(attrs['tenant_id'])
        return attrs

class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    tenant_id = serializers.CharField(write_only=True)
    tenant_name = serializers.CharField(read_only=True)
    student_id = serializers.CharField(write_only=True)
    student_name = serializers.CharField(read_only=True)
    assignment = AssignmentBriefSerializer(read_only=True)
    assignment_id = serializers.PrimaryKeyRelatedField(queryset=Assignment.objects.all(), source='assignment', write_only=True)
    submission_file_url = serializers.CharField(read_only=True)

    class Meta:
        model = AssignmentSubmission
        fields = [
            'id', 'tenant_id', 'tenant_name', 'assignment', 'assignment_id', 'student_id', 'student_name',
            'submitted_at', 'submission_file', 'submission_file_url', 'response_text', 'grade', 'feedback', 'is_graded'
        ]
        read_only_fields = ['tenant_name', 'student_name', 'submitted_at', 'grade', 'feedback', 'is_graded', 'submission_file_url']

    def validate(self, attrs):
        attrs['tenant_name'] = validate_tenant_id(attrs['tenant_id'])
        validate_user_id(attrs['student_id'], attrs['tenant_id'])
        return attrs

    def create(self, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        student_id = validated_data.pop('student_id')
        submission_file = validated_data.pop('submission_file', None)
        instance = super().create(validated_data)
        if submission_file:
            file_name = f"courses/{instance.assignment.course.tenant_id}/{instance.assignment.course.slug}/assignments/submissions/{uuid.uuid4().hex}_{submission_file.name}"
            try:
                storage_service = get_storage_service()
                storage_service.upload_file(submission_file, file_name, content_type=submission_file.content_type)
                instance.submission_file = file_name
                instance.submission_file_url = storage_service.get_public_url(file_name)
                instance.save()
                ActivityLog.objects.create(
                    tenant_id=tenant_id,
                    tenant_name=tenant_name,
                    user_id=student_id,
                    activity_type='assignmentsubmission_created',
                    details=f"AssignmentSubmission for assignment {instance.assignment.title} created",
                    status='success'
                )
            except Exception as e:
                logger.error(f"[Tenant {tenant_id}] Failed to upload submission file: {str(e)}")
                raise serializers.ValidationError("Failed to upload submission file")
        return instance

    def update(self, instance, validated_data):
        tenant_id = validated_data.pop('tenant_id')
        tenant_name = validated_data.pop('tenant_name')
        student_id = validated_data.pop('student_id')
        submission_file = validated_data.pop('submission_file', None)
        instance = super().update(instance, validated_data)
        if submission_file:
            storage_service = get_storage_service()
            if instance.submission_file:
                storage_service.delete_file(instance.submission_file)
            file_name = f"courses/{instance.assignment.course.tenant_id}/{instance.assignment.course.slug}/assignments/submissions/{uuid.uuid4().hex}_{submission_file.name}"
            try:
                storage_service.upload_file(submission_file, file_name, content_type=submission_file.content_type)
                instance.submission_file = file_name
                instance.submission_file_url = storage_service.get_public_url(file_name)
                instance.save()
                ActivityLog.objects.create(
                    tenant_id=tenant_id,
                    tenant_name=tenant_name,
                    user_id=student_id,
                    activity_type='assignmentsubmission_updated',
                    details=f"AssignmentSubmission for assignment {instance.assignment.title} updated",
                    status='success'
                )
            except Exception as e:
                logger.error(f"[Tenant {tenant_id}] Failed to upload submission file: {str(e)}")
                raise serializers.ValidationError("Failed to upload submission file")
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['submission_file_url'] = instance.submission_file_url or ''
        if instance.student_id:
            try:
                response = requests.get(
                    f"{settings.AUTH_SERVICE_URL}/api/user/users/{instance.student_id}/",
                    headers={"X-Tenant-ID": instance.tenant_id},
                    timeout=5
                )
                if response.status_code == 200:
                    user_data = response.json()
                    representation['student_name'] = user_data.get('username', '')
            except requests.RequestException as e:
                logger.error(f"Failed to fetch student_name for user {instance.student_id}: {str(e)}")
                representation['student_name'] = ''
        return representation