# Standard library
import logging
from datetime import timedelta
from typing import Any, Dict
# Third-party
import jwt
import requests
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django_tenants.utils import tenant_context
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
import uuid

from decimal import Decimal
# Local imports
from core.models import Branch, Domain, Tenant, GlobalActivity
from utils.supabase import upload_file_dynamic
from .models import (DocumentAcknowledgment, DocumentPermission, Document,
    DocumentVersion, BlockedIP, ClientProfile, WithdrawalDetail, Group, GroupMembership,
    CustomUser, DrivingRiskAssessment, EducationDetail,
    EmploymentDetail, InvestmentDetail, InsuranceVerification, LegalWorkEligibility,
    OtherUserDocuments, PasswordResetToken,
    ProfessionalQualification, ProofOfAddress, ReferenceCheck,
    SkillDetail, UserActivity, UserProfile, UserSession,
)
# Logger
import os
logger = logging.getLogger(__name__)


def get_user_data_from_jwt(request):
    """Extract user data from the authenticated request user."""
    if not request.user or not request.user.is_authenticated:
        logger.warning("No authenticated user available in request")
        raise serializers.ValidationError("Authentication required. No user found in request.")
    
    user = request.user
    logger.info(f"Extracting user data from request user: {user.email}, ID: {user.id}")
    
    return {
        'email': user.email,
        'first_name': user.first_name or '',
        'last_name': user.last_name or '',
        'job_role': getattr(user, 'job_role', ''),
        'id': user.id  # Keep as numeric ID
    }    

def get_tenant_id_from_jwt(request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise serializers.ValidationError("No valid Bearer token provided.")
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("tenant_unique_id")
    except Exception as e:
        logger.error(f"Invalid JWT token: {str(e)}")
        raise serializers.ValidationError("Invalid JWT token.")

def get_last_updated_by(self, obj):
    if obj.last_updated_by_id:
        try:
            # Try to get by id if it's numeric, otherwise by email
            if str(obj.last_updated_by_id).isdigit():
                updater = CustomUser.objects.get(id=int(obj.last_updated_by_id))
            else:
                updater = CustomUser.objects.get(email=obj.last_updated_by_id)
            return {
                'id': updater.id,
                'email': updater.email,
                'first_name': updater.first_name,
                'last_name': updater.last_name
            }
        except CustomUser.DoesNotExist:
            logger.warning(f"User {obj.last_updated_by_id} not found")
            return None
        except ValueError:
            logger.warning(f"Invalid last_updated_by_id format: {obj.last_updated_by_id}")
            return None
    logger.warning(f"No last_updated_by_id provided for {obj}")
    return None

def validate_file_extension(value):
    if value:
        ext = os.path.splitext(value.name)[1].lower()
        valid_extensions = ['.pdf', '.png', '.jpg', '.jpeg']
        if ext not in valid_extensions:
            raise serializers.ValidationError('Only PDF, PNG, JPG, and JPEG files are allowed.')
        if value.size > 2 * 1024 * 1024:  # 2MB limit
            raise serializers.ValidationError('File size cannot exceed 2MB.')
        if value.size == 0:
            raise serializers.ValidationError('File cannot be empty.')
    return value


class ProfessionalQualificationSerializer(serializers.ModelSerializer):
    #image_file = serializers.FileField(required=False, allow_null=True)
    image_file = serializers.FileField(required=False, allow_null=True, validators=[validate_file_extension])
    last_updated_by = serializers.SerializerMethodField()

    class Meta:
        model = ProfessionalQualification
        fields = ["id", "name", "image_file", "image_file_url", "last_updated_by_id", "last_updated_by"]
        read_only_fields = ["id", "last_updated_by", "last_updated_by_id"]
        extra_kwargs = {
            "name": {"required": True},
            "image_file": {"required": False, "allow_null": True},
        }

    def get_last_updated_by(self, obj):
        return get_last_updated_by(self, obj)

    def create(self, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            validated_data['last_updated_by_id'] = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for creation")
            raise serializers.ValidationError({"last_updated_by_id": "User ID required for creation."})

        image = validated_data.pop("image_file", None)
        if image:
            logger.info(f"Uploading professional qualification image: {image.name}")
            url = upload_file_dynamic(
                image, image.name, content_type=getattr(image, "content_type", "application/octet-stream")
            )
            validated_data["image_file_url"] = url
            validated_data["image_file"] = None  # Don't save to ImageField
            logger.info(f"Professional qualification image uploaded: {url}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            instance.last_updated_by_id = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for update")

        image = validated_data.pop("image_file", None)
        if image:
            logger.info(f"Updating professional qualification image: {image.name}")
            url = upload_file_dynamic(
                image, image.name, content_type=getattr(image, "content_type", "application/octet-stream")
            )
            validated_data["image_file_url"] = url
            validated_data["image_file"] = None  # Don't save to ImageField
            logger.info(f"Professional qualification image updated: {url}")
        return super().update(instance, validated_data)

    def validate(self, data):
        logger.info(f"Validating ProfessionalQualificationSerializer data: {data}")
        return super().validate(data)


class EducationDetailSerializer(serializers.ModelSerializer):
    #certificate = serializers.FileField(required=False, allow_null=True)
    certificate = serializers.FileField(required=False, allow_null=True, validators=[validate_file_extension])
    start_year = serializers.IntegerField(required=False, allow_null=True)
    end_year = serializers.IntegerField(required=False, allow_null=True)
    last_updated_by = serializers.SerializerMethodField()

    class Meta:
        model = EducationDetail
        fields = ["id", "institution", "highest_qualification", "course_of_study", "start_year", "end_year", "start_year_new", "end_year_new", "certificate", "certificate_url", "skills", "last_updated_by_id", "last_updated_by"]
        read_only_fields = ["id", "last_updated_by", "last_updated_by_id"]
        extra_kwargs = {
            "institution": {"required": True},
            "highest_qualification": {"required": True},
            "course_of_study": {"required": True},
            "start_year": {"required": False},
            "end_year": {"required": False},
            "start_year_new": {"required": False},
            "end_year_new": {"required": False},
            "skills": {"required": False, "allow_null": True},
            "certificate": {"required": False, "allow_null": True},
        }

    def get_last_updated_by(self, obj):
        return get_last_updated_by(self, obj)

    def create(self, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            validated_data['last_updated_by_id'] = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for creation")
            raise serializers.ValidationError({"last_updated_by_id": "User ID required for creation."})

        certificate = validated_data.pop("certificate", None)
        if certificate:
            logger.info(f"Uploading education certificate: {certificate.name}")
            url = upload_file_dynamic(
                certificate,
                certificate.name,
                content_type=getattr(certificate, "content_type", "application/octet-stream"),
            )
            validated_data["certificate_url"] = url
            validated_data["certificate"] = None  # Don't save to ImageField
            logger.info(f"Education certificate uploaded: {url}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            instance.last_updated_by_id = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for update")

        certificate = validated_data.pop("certificate", None)
        if certificate:
            logger.info(f"Updating education certificate: {certificate.name}")
            url = upload_file_dynamic(
                certificate,
                certificate.name,
                content_type=getattr(certificate, "content_type", "application/octet-stream"),
            )
            validated_data["certificate_url"] = url
            validated_data["certificate"] = None  # Don't save to ImageField
            logger.info(f"Education certificate updated: {url}")
        return super().update(instance, validated_data)

    def validate(self, data):
        logger.info(f"Validating EducationDetailSerializer data: {data}")
        start_year = data.get("start_year")
        end_year = data.get("end_year")

        # Validate year ranges

        # Validate year ranges
        if start_year is not None:
            if start_year < 1900 or start_year > 2100:
                raise serializers.ValidationError({"start_year": "Start year must be between 1900 and 2100."})
        if end_year is not None:
            if end_year < 1900 or end_year > 2100:
                raise serializers.ValidationError({"end_year": "End year must be between 1900 and 2100."})

        # Validate logical relationship
        if start_year and end_year and start_year > end_year:
            raise serializers.ValidationError({"start_year": "Start year cannot be greater than end year."})
        return super().validate(data)


class SkillDetailSerializer(serializers.ModelSerializer):
    certificate = serializers.FileField(required=False, allow_null=True, validators=[validate_file_extension])
    last_updated_by = serializers.SerializerMethodField()

    class Meta:
        model = SkillDetail
        fields = ["id", "skill_name", "proficiency_level", "description", "acquired_date", "years_of_experience", "certificate", "certificate_url", "last_updated_by_id", "last_updated_by"]
        read_only_fields = ["id", "last_updated_by", "last_updated_by_id"]
        extra_kwargs = {
            "skill_name": {"required": True},
            "proficiency_level": {"required": False, "allow_null": True},
            "description": {"required": False, "allow_null": True},
            "acquired_date": {"required": False, "allow_null": True},
            "years_of_experience": {"required": False, "allow_null": True},
            "certificate": {"required": False, "allow_null": True},
        }

    def get_last_updated_by(self, obj):
        return get_last_updated_by(self, obj)

    def create(self, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            validated_data['last_updated_by_id'] = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for creation")
            raise serializers.ValidationError({"last_updated_by_id": "User ID required for creation."})

        certificate = validated_data.pop("certificate", None)
        if certificate:
            logger.info(f"Uploading skill certificate: {certificate.name}")
            url = upload_file_dynamic(
                certificate,
                certificate.name,
                content_type=getattr(certificate, "content_type", "application/octet-stream"),
            )
            validated_data["certificate_url"] = url
            validated_data["certificate"] = None  # Don't save to ImageField
            logger.info(f"Skill certificate uploaded: {url}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            instance.last_updated_by_id = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for update")

        certificate = validated_data.pop("certificate", None)
        if certificate:
            logger.info(f"Updating skill certificate: {certificate.name}")
            url = upload_file_dynamic(
                certificate,
                certificate.name,
                content_type=getattr(certificate, "content_type", "application/octet-stream"),
            )
            validated_data["certificate_url"] = url
            validated_data["certificate"] = None  # Don't save to ImageField
            logger.info(f"Skill certificate updated: {url}")
        return super().update(instance, validated_data)

    def validate(self, data):
        logger.info(f"Validating SkillDetailSerializer data: {data}")
        years_of_experience = data.get("years_of_experience")
        if years_of_experience is not None:
            if years_of_experience < 0:
                raise serializers.ValidationError({"years_of_experience": "Years of experience cannot be negative."})
            if years_of_experience > 50:
                raise serializers.ValidationError({"years_of_experience": "Years of experience cannot exceed 50."})
        return super().validate(data)


class EmploymentDetailSerializer(serializers.ModelSerializer):
    last_updated_by = serializers.SerializerMethodField()

    class Meta:
        model = EmploymentDetail
        exclude = ["user_profile"]
        extra_kwargs = {
            "job_role": {"required": True},
            "hierarchy": {"required": False, "allow_blank": True},
            "department": {"required": False, "allow_blank": True},
            "line_manager": {"required": False, "allow_blank": True},
            "work_email": {"required": True},
            "employment_type": {"required": False, "allow_blank": True},
            "employment_start_date": {"required": True},
            "salary": {"required": False, "allow_null": True},
            "working_days": {"required": True},
            "maximum_working_hours": {"required": True},
            "employment_end_date": {"required": False, "allow_null": True},
            "probation_end_date": {"required": False, "allow_null": True},
            "line_manager": {"required": False, "allow_null": True},
            "currency": {"required": False, "allow_null": True},
            "salary_rate": {"required": False, "allow_null": True},
        }
        read_only_fields = ["last_updated_by", "last_updated_by_id"]

    def get_last_updated_by(self, obj):
        return get_last_updated_by(self, obj)

    def create(self, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            validated_data['last_updated_by_id'] = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for creation")
            raise serializers.ValidationError({"last_updated_by_id": "User ID required for creation."})
        return super().create(validated_data)

    def update(self, instance, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            instance.last_updated_by_id = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for update")
        return super().update(instance, validated_data)

    def validate(self, data):
        logger.info(f"Validating EmploymentDetailSerializer data: {data}")
        return super().validate(data)


class ReferenceCheckSerializer(serializers.ModelSerializer):
    last_updated_by = serializers.SerializerMethodField()

    class Meta:
        model = ReferenceCheck
        exclude = ["user_profile"]
        extra_kwargs = {
            "name": {"required": True},
            "phone_number": {"required": True},
            "email": {"required": True},
            "relationship_to_applicant": {"required": True},
        }
        read_only_fields = ["last_updated_by", "last_updated_by_id"]

    def get_last_updated_by(self, obj):
        return get_last_updated_by(self, obj)

    def create(self, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            validated_data['last_updated_by_id'] = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for creation")
            raise serializers.ValidationError({"last_updated_by_id": "User ID required for creation."})
        return super().create(validated_data)

    def update(self, instance, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            instance.last_updated_by_id = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for update")
        return super().update(instance, validated_data)

    def validate(self, data):
        logger.info(f"Validating ReferenceCheckSerializer data: {data}")
        return super().validate(data)

class ProofOfAddressSerializer(serializers.ModelSerializer):
    # document = serializers.FileField(required=False, allow_null=True)
    # nin_document = serializers.FileField(required=False, allow_null=True)
    document = serializers.FileField(required=False, allow_null=True, validators=[validate_file_extension])
    nin_document = serializers.FileField(required=False, allow_null=True, validators=[validate_file_extension])
    last_updated_by = serializers.SerializerMethodField()

    class Meta:
        model = ProofOfAddress
        fields = ["id", "type", "document", "document_url", "issue_date", "nin_document", "nin_document_url", "last_updated_by_id", "last_updated_by"]
        read_only_fields = ["id", "last_updated_by", "last_updated_by_id"]
        extra_kwargs = {field: {"required": False, "allow_null": True} for field in ["type", "issue_date", "nin"]}

    def get_last_updated_by(self, obj):
        return get_last_updated_by(self, obj)

    def create(self, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            validated_data['last_updated_by_id'] = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for creation")
            raise serializers.ValidationError({"last_updated_by_id": "User ID required for creation."})

        document = validated_data.pop("document", None)
        nin_document = validated_data.pop("nin_document", None)
        if document:
            logger.info(f"Uploading proof of address document: {document.name}")
            url = upload_file_dynamic(
                document, document.name, content_type=getattr(document, "content_type", "application/octet-stream")
            )
            validated_data["document_url"] = url
            validated_data["document"] = None  # Don't save to ImageField
            logger.info(f"Proof of address document uploaded: {url}")
        if nin_document:
            logger.info(f"Uploading proof of address NIN document: {nin_document.name}")
            url = upload_file_dynamic(
                nin_document,
                nin_document.name,
                content_type=getattr(nin_document, "content_type", "application/octet-stream"),
            )
            validated_data["nin_document_url"] = url
            validated_data["nin_document"] = None  # Don't save to ImageField
            logger.info(f"Proof of address NIN document uploaded: {url}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            instance.last_updated_by_id = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for update")

        document = validated_data.pop("document", None)
        nin_document = validated_data.pop("nin_document", None)
        if document:
            logger.info(f"Updating proof of address document: {document.name}")
            url = upload_file_dynamic(
                document, document.name, content_type=getattr(document, "content_type", "application/octet-stream")
            )
            validated_data["document_url"] = url
            validated_data["document"] = None  # Don't save to ImageField
            logger.info(f"Proof of address document updated: {url}")
        if nin_document:
            logger.info(f"Updating proof of address NIN document: {nin_document.name}")
            url = upload_file_dynamic(
                nin_document,
                nin_document.name,
                content_type=getattr(nin_document, "content_type", "application/octet-stream"),
            )
            validated_data["nin_document_url"] = url
            validated_data["nin_document"] = None  # Don't save to ImageField
            logger.info(f"Proof of address NIN document updated: {url}")
        return super().update(instance, validated_data)


class InsuranceVerificationSerializer(serializers.ModelSerializer):
    document = serializers.FileField(required=False, allow_null=True, validators=[validate_file_extension])
    last_updated_by = serializers.SerializerMethodField()

    class Meta:
        model = InsuranceVerification
        fields = ["id", "insurance_type", "document", "document_url", "provider_name", "coverage_start_date", "expiry_date", "phone_number", "last_updated_by_id", "last_updated_by"]
        read_only_fields = ["id", "last_updated_by", "last_updated_by_id"]
        extra_kwargs = {
            field: {"required": False, "allow_null": True}
            for field in ["insurance_type", "provider_name", "coverage_start_date", "expiry_date", "phone_number"]
        }

    def get_last_updated_by(self, obj):
        return get_last_updated_by(self, obj)

    def create(self, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            validated_data['last_updated_by_id'] = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for creation")
            raise serializers.ValidationError({"last_updated_by_id": "User ID required for creation."})

        document = validated_data.pop("document", None)
        if document:
            logger.info(f"Uploading insurance document: {document.name}")
            url = upload_file_dynamic(
                document, document.name, content_type=getattr(document, "content_type", "application/octet-stream")
            )
            validated_data["document_url"] = url
            validated_data["document"] = None  # Don't save to ImageField
            logger.info(f"Insurance document uploaded: {url}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            instance.last_updated_by_id = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for update")

        document = validated_data.pop("document", None)
        if document:
            logger.info(f"Updating insurance document: {document.name}")
            url = upload_file_dynamic(
                document, document.name, content_type=getattr(document, "content_type", "application/octet-stream")
            )
            validated_data["document_url"] = url
            validated_data["document"] = None  # Don't save to ImageField
            logger.info(f"Insurance document updated: {url}")
        return super().update(instance, validated_data)


class DrivingRiskAssessmentSerializer(serializers.ModelSerializer):
    last_updated_by = serializers.SerializerMethodField()
    supporting_document = serializers.FileField(required=False, allow_null=True, validators=[validate_file_extension])

    class Meta:
        model = DrivingRiskAssessment
        fields = ["id", "assessment_date", "fuel_card_usage_compliance", "road_traffic_compliance", "tracker_usage_compliance", "maintenance_schedule_compliance", "additional_notes", "supporting_document", "supporting_document_url", "last_updated_by_id", "last_updated_by"]
        read_only_fields = ["id", "last_updated_by", "last_updated_by_id"]
        extra_kwargs = {
            field: {"required": False, "allow_null": True}
            for field in ["assessment_date", "fuel_card_usage_compliance", "road_traffic_compliance", "tracker_usage_compliance", "maintenance_schedule_compliance", "additional_notes"]
        }

    def get_last_updated_by(self, obj):
        return get_last_updated_by(self, obj)

    def create(self, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            validated_data['last_updated_by_id'] = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for creation")
            raise serializers.ValidationError({"last_updated_by_id": "User ID required for creation."})

        supporting_document = validated_data.pop("supporting_document", None)
        if supporting_document:
            logger.info(f"Uploading driving risk assessment document: {supporting_document.name}")
            url = upload_file_dynamic(
                supporting_document,
                supporting_document.name,
                content_type=getattr(supporting_document, "content_type", "application/octet-stream"),
            )
            validated_data["supporting_document_url"] = url
            validated_data["supporting_document"] = None  # Don't save to ImageField
            logger.info(f"Driving risk assessment document uploaded: {url}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            instance.last_updated_by_id = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for update")

        supporting_document = validated_data.pop("supporting_document", None)
        if supporting_document:
            logger.info(f"Updating driving risk assessment document: {supporting_document.name}")
            url = upload_file_dynamic(
                supporting_document,
                supporting_document.name,
                content_type=getattr(supporting_document, "content_type", "application/octet-stream"),
            )
            validated_data["supporting_document_url"] = url
            validated_data["supporting_document"] = None  # Don't save to ImageField
            logger.info(f"Driving risk assessment document updated: {url}")
        return super().update(instance, validated_data)


class LegalWorkEligibilitySerializer(serializers.ModelSerializer):
    document = serializers.FileField(required=False, allow_null=True, validators=[validate_file_extension])
    last_updated_by = serializers.SerializerMethodField()

    class Meta:
        model = LegalWorkEligibility
        fields = ["id", "evidence_of_right_to_rent", "document", "document_url", "expiry_date", "phone_number", "last_updated_by_id", "last_updated_by"]
        read_only_fields = ["id", "last_updated_by", "last_updated_by_id"]
        extra_kwargs = {
            field: {"required": False, "allow_null": True}
            for field in ["evidence_of_right_to_rent", "expiry_date", "phone_number"]
        }

    def get_last_updated_by(self, obj):
        return get_last_updated_by(self, obj)

    def create(self, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            validated_data['last_updated_by_id'] = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for creation")
            raise serializers.ValidationError({"last_updated_by_id": "User ID required for creation."})

        document = validated_data.pop("document", None)
        if document:
            logger.info(f"Uploading legal work eligibility document: {document.name}")
            url = upload_file_dynamic(
                document, document.name, content_type=getattr(document, "content_type", "application/octet-stream")
            )
            validated_data["document_url"] = url
            validated_data["document"] = None  # Don't save to ImageField
            logger.info(f"Legal work eligibility document uploaded: {url}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            instance.last_updated_by_id = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for update")

        document = validated_data.pop("document", None)
        if document:
            logger.info(f"Updating legal work eligibility document: {document.name}")
            url = upload_file_dynamic(
                document, document.name, content_type=getattr(document, "content_type", "application/octet-stream")
            )
            validated_data["document_url"] = url
            validated_data["document"] = None  # Don't save to ImageField
            logger.info(f"Legal work eligibility document updated: {url}")
        return super().update(instance, validated_data)


class OtherUserDocumentsSerializer(serializers.ModelSerializer):
    last_updated_by = serializers.SerializerMethodField()
    file = serializers.FileField(required=False, allow_null=True, validators=[validate_file_extension])
    title = serializers.CharField(required=False, allow_null=True)
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = OtherUserDocuments
        fields = ["id", "government_id_type", "title", "document_number", "expiry_date", "file", "file_url", "branch", "last_updated_by_id", "last_updated_by"]
        read_only_fields = ["id", "last_updated_by", "last_updated_by_id"]

    def create(self, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            validated_data['last_updated_by_id'] = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for creation")
            raise serializers.ValidationError({"last_updated_by_id": "User ID required for creation."})

        file = validated_data.pop("file", None)
        if file:
            logger.info(f"Uploading other user document: {file.name}")
            url = upload_file_dynamic(
                file, file.name, content_type=getattr(file, "content_type", "application/octet-stream")
            )
            validated_data["file_url"] = url
            validated_data["file"] = None  # Don't save to FileField
            logger.info(f"Other user document uploaded: {url}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            instance.last_updated_by_id = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for update")

        file = validated_data.pop("file", None)
        if file:
            logger.info(f"Updating other user document: {file.name}")
            url = upload_file_dynamic(
                file, file.name, content_type=getattr(file, "content_type", "application/octet-stream")
            )
            validated_data["file_url"] = url
            validated_data["file"] = None  # Don't save to FileField
            logger.info(f"Other user document updated: {url}")
        return super().update(instance, validated_data)
    

class InvestmentDetailSerializer(serializers.ModelSerializer):
    last_updated_by = serializers.SerializerMethodField()
    monthly_interest_amount = serializers.SerializerMethodField()

    class Meta:
        model = InvestmentDetail
        fields = [
            "id", "roi_rate", "custom_roi_rate", "investment_amount",
            "investment_start_date", "remaining_balance","monthly_interest_amount",
            "last_updated_by_id", "last_updated_by"
        ]
        read_only_fields = ["id", "last_updated_by", "last_updated_by_id", "remaining_balance"]

    def get_last_updated_by(self, obj):
        return get_last_updated_by(self, obj)
    
    def get_monthly_interest_amount(self, obj):
        """Calculate monthly interest: (40% of principal) / 12"""
        return (obj.investment_amount * Decimal('0.40')) / 12
    

    def create(self, validated_data, **kwargs):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            validated_data['last_updated_by_id'] = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for creation")
            raise serializers.ValidationError({"last_updated_by_id": "User ID required for creation."})
        instance = super().create(validated_data)
        user_profile = kwargs.get('user_profile')
        if user_profile:
            instance.user_profile = user_profile
            instance.save(update_fields=['user_profile'])
        return instance

        

    def update(self, instance, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            instance.last_updated_by_id = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for update")
        return super().update(instance, validated_data)

    def validate(self, data):
        logger.info(f"Validating InvestmentDetailSerializer data: {data}")
        return super().validate(data)     

class WithdrawalDetailSerializer(serializers.ModelSerializer):
    last_updated_by = serializers.SerializerMethodField()
    # ✅ Include investment for dependency
    investment = serializers.PrimaryKeyRelatedField(queryset=InvestmentDetail.objects.all())

    class Meta:
        model = WithdrawalDetail
        fields = [
            "id", "investment", "withdrawal_amount",
            "withdrawal_request_date", "withdrawal_approved_date", "withdrawal_approved",
            "withdrawal_approved_by", "withdrawn_date", "withdrawan",
            "last_updated_by_id", "last_updated_by"
        ]
        read_only_fields = ["id", "user_profile", "last_updated_by", "last_updated_by_id"]  # user_profile auto-derived

    def get_last_updated_by(self, obj):
        return get_last_updated_by(self, obj)  # Reuse your existing function

    def validate(self, data):
        investment = data.get('investment')
        withdrawal_amount = data.get('withdrawal_amount')

        if not investment:
            raise serializers.ValidationError({"investment": "Withdrawal requires an associated investment."})

        # ✅ ENFORCE DEPENDENCY: Check available balance
        available = investment.remaining_balance
        if withdrawal_amount > available:
            raise serializers.ValidationError({
                "withdrawal_amount": f"Amount exceeds available balance (${available})."
            })

        # ✅ NEW: Role validation for approval
        request = self.context['request']
        current_user = request.user
        if 'withdrawal_approved' in data and data['withdrawal_approved']:
            if current_user.role not in ['staff', 'admin']:
                raise serializers.ValidationError({
                    "withdrawal_approved": "Only staff or admin can approve withdrawals."
                })

        return data

    def create(self, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            validated_data['last_updated_by_id'] = str(user_id)
        else:
            raise serializers.ValidationError({"last_updated_by_id": "User ID required."})

        # ✅ NEW: If approved on create (unlikely, but handle)
        if validated_data.get('withdrawal_approved'):
            approver_data = {
                'id': str(user_id),
                'email': user_data['email'],
                'first_name': user_data['first_name'],
                'last_name': user_data['last_name'],
                'role': self.context['request'].user.role
            }
            validated_data['withdrawal_approved_by'] = approver_data
            validated_data['withdrawal_approved_date'] = timezone.now()

        return super().create(validated_data)

    def update(self, instance, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            instance.last_updated_by_id = str(user_id)

        # ✅ NEW: Populate approver details on approval
        if 'withdrawal_approved' in validated_data and validated_data['withdrawal_approved']:
            approver_data = {
                'id': str(user_id),
                'email': user_data['email'],
                'first_name': user_data['first_name'],
                'last_name': user_data['last_name'],
                'role': self.context['request'].user.role
            }
            instance.withdrawal_approved_by = approver_data
            instance.withdrawal_approved_date = timezone.now()
            # Optionally set withdrawan to True if approved
            validated_data['withdrawan'] = True

        # ✅ REFRESH: Re-validate balance on update
        self.validate(validated_data)  # Re-run validation
        return super().update(instance, validated_data)
     

class UserProfileSerializer(serializers.ModelSerializer):
    professional_qualifications = ProfessionalQualificationSerializer(many=True, required=False, allow_null=True)
    employment_details = EmploymentDetailSerializer(many=True, required=False, allow_null=True)
    investment_details = InvestmentDetailSerializer(many=True, required=False, allow_null=True)
    withdrawal_details = WithdrawalDetailSerializer(many=True, required=False, allow_null=True)
    education_details = EducationDetailSerializer(many=True, required=False, allow_null=True)
    skills = SkillDetailSerializer(many=True, required=False, allow_null=True)
    reference_checks = ReferenceCheckSerializer(many=True, required=False, allow_null=True)
    proof_of_address = ProofOfAddressSerializer(many=True, required=False, allow_null=True)
    insurance_verifications = InsuranceVerificationSerializer(many=True, required=False, allow_null=True)
    driving_risk_assessments = DrivingRiskAssessmentSerializer(many=True, required=False, allow_null=True)
    legal_work_eligibilities = LegalWorkEligibilitySerializer(many=True, required=False, allow_null=True)
    other_user_documents = OtherUserDocumentsSerializer(many=True, required=False, allow_null=True)
    last_updated_by = serializers.SerializerMethodField()


    # Update all file fields in UserProfile
    profile_image = serializers.FileField(required=False, allow_null=True, validators=[validate_file_extension])
    drivers_licence_image1 = serializers.FileField(required=False, allow_null=True, validators=[validate_file_extension])
    drivers_licence_image2 = serializers.FileField(required=False, allow_null=True, validators=[validate_file_extension])
    Right_to_Work_file = serializers.FileField(required=False, allow_null=True, validators=[validate_file_extension])
    Right_to_rent_file = serializers.FileField(required=False, allow_null=True, validators=[validate_file_extension])
    dbs_certificate = serializers.FileField(required=False, allow_null=True, validators=[validate_file_extension])
    dbs_update_file = serializers.FileField(required=False, allow_null=True, validators=[validate_file_extension])

    # Availability field as JSONField
    availability = serializers.JSONField(required=False, allow_null=True)


    class Meta:
        model = UserProfile
        fields = [
            "id",
            "user",
            "salary_rate",
            "availability",  # New field added
            "work_phone",
            "personal_phone",
            "policy_number",
            "gender",
            "dob",
            "street",
            "city",
            "state",
            "country",
            "zip_code",
            "department",
            "employee_id",
            "marital_status",
            "profile_image",
            "profile_image_url",
            "is_driver",
            "type_of_vehicle",
            "drivers_licence_image1",
            "drivers_licence_image1_url",
            "drivers_licence_image2",
            "drivers_licence_image2_url",
            "drivers_licence_country_of_issue",
            "drivers_licence_date_issue",
            "drivers_licence_expiry_date",
            "drivers_license_insurance_provider",
            "drivers_licence_insurance_expiry_date",
            "drivers_licence_issuing_authority",
            "drivers_licence_policy_number",
            "assessor_name",
            "manual_handling_risk",
            "lone_working_risk",
            "infection_risk",
            "next_of_kin",
            "next_of_kin_address",
            "next_of_kin_phone_number",
            "next_of_kin_alternate_phone",
            "relationship_to_next_of_kin",
            "next_of_kin_email",
            "next_of_kin_town",
            "next_of_kin_zip_code",
            "Right_to_Work_status",
            "Right_to_Work_passport_holder",
            "Right_to_Work_document_type",
            "Right_to_Work_share_code",
            "Right_to_Work_document_number",
            "Right_to_Work_document_expiry_date",
            "Right_to_Work_country_of_issue",
            "Right_to_Work_file",
            "Right_to_Work_file_url",
            "Right_to_rent_file",
            "Right_to_rent_file_url",
            "Right_to_Work_restrictions",
            "dbs_type",
            "dbs_certificate",
            "dbs_certificate_url",
            "dbs_certificate_number",
            "dbs_issue_date",
            "dbs_update_file",
            "dbs_update_file_url",
            "dbs_update_certificate_number",
            "dbs_update_issue_date",
            "dbs_status_check",
            "bank_name",
            "account_number",
            "account_name",
            "account_type",
            "country_of_bank_account",
            "routing_number",
            "ssn_last4",
            "sort_code",
            "iban",
            "bic_swift",
            "national_insurance_number",
            "consent_given",
            "bank_details_submitted_at",

            "access_duration",
            "system_access_rostering",
            "system_access_hr",
            "system_access_recruitment",
            "system_access_training",
            "system_access_finance",
            "system_access_compliance",
            "system_access_co_superadmin",
            "system_access_asset_management",
            "vehicle_type",
            "professional_qualifications",
            "employment_details",
            "education_details",
            "skills",
            "investment_details",
            "withdrawal_details",
            "reference_checks",
            "proof_of_address",
            "insurance_verifications",
            "driving_risk_assessments",
            "legal_work_eligibilities",
            "other_user_documents",
            "last_updated_by_id",
            "last_updated_by",
        ]
        read_only_fields = ["id", "user", "employee_id", "last_updated_by", "last_updated_by_id"]
        extra_kwargs = {
            field: {"required": False, "allow_null": True}
            for field in [
                "salary_rate",
                "availability",  # New field, optional
                "drivers_licence_date_issue",
                "drivers_licence_expiry_date",
                "drivers_licence_country_of_issue",
                "drivers_license_insurance_provider",
                "drivers_licence_insurance_expiry_date",
                "drivers_licence_issuing_authority",
                "drivers_licence_policy_number",
                "work_phone",
                "policy_number",
                "personal_phone",
                "gender",
                "dob",
                "street",
                "city",
                "state",
                "country",
                "zip_code",
                "department",
                "marital_status",
                "is_driver",
                "type_of_vehicle",
                "assessor_name",
                "manual_handling_risk",
                "lone_working_risk",
                "infection_risk",
                "next_of_kin",
                "next_of_kin_address",
                "next_of_kin_phone_number",
                "next_of_kin_alternate_phone",
                "relationship_to_next_of_kin",
                "next_of_kin_email",
                "next_of_kin_town",
                "next_of_kin_zip_code",
                "Right_to_Work_status",
                "Right_to_Work_passport_holder",
                "Right_to_Work_document_type",
                "Right_to_Work_share_code",
                "Right_to_Work_document_number",
                "Right_to_Work_document_expiry_date",
                "Right_to_Work_country_of_issue",
                "Right_to_Work_restrictions",
                "dbs_type",
                "dbs_certificate_number",
                "dbs_issue_date",
                "dbs_update_certificate_number",
                "dbs_update_issue_date",
                "dbs_status_check",
                "bank_name",
                "account_number",
                "account_name",
                "account_type",
                

                "country_of_bank_account",
                "routing_number",
                "us_account_number",
                "us_account_type",
                "ssn_last4",
                "sort_code",
                "uk_account_number",
                "iban",
                "bic_swift",
                "national_insurance_number",
                "consent_given",
                "bank_details_submitted_at",



                "access_duration",
                "system_access_rostering",
                "system_access_hr",
                "system_access_recruitment",
                "system_access_training",
                "system_access_finance",
                "system_access_compliance",
                "system_access_co_superadmin",
                "system_access_asset_management",
                "vehicle_type",
                "profile_image_url",
                "drivers_licence_image1_url",
                "drivers_licence_image2_url",
                "Right_to_Work_file_url",
                "Right_to_rent_file_url",
                "dbs_certificate_url",
                "dbs_update_file_url",
            ]
        }

    def get_last_updated_by(self, obj):
        return get_last_updated_by(self, obj)

    def validate(self, data):
        logger.info(f"Validating UserProfileSerializer data: {data}")
        nested_fields = [
            "professional_qualifications",
            "employment_details",
            "education_details",
            "skills",
            "investment_details",
            "withdrawal_details",
            "reference_checks",
            "proof_of_address",
            "insurance_verifications",
            "driving_risk_assessments",
            "legal_work_eligibilities",
            "other_user_documents",
        ]
        for field in nested_fields:
            if field in data and data[field] is not None and len(data[field]) == 0:
                logger.warning(f"Empty array provided for {field}")
        # Optional: Add validation for availability structure if needed
        # e.g., if 'availability' in data and not isinstance(data['availability'], dict):
        #     raise serializers.ValidationError({"availability": "Must be a JSON object."})
        return super().validate(data)

    def create(self, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            validated_data['last_updated_by_id'] = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for creation")
            raise serializers.ValidationError({"last_updated_by_id": "User ID required for creation."})

        logger.info(f"Creating UserProfile with validated data: {validated_data}")
        nested_fields = [
            ("professional_qualifications", ProfessionalQualificationSerializer, "professional_qualifications"),
            ("employment_details", EmploymentDetailSerializer, "employment_details"),
            ("education_details", EducationDetailSerializer, "education_details"),
            ("skills", SkillDetailSerializer, "skill_details"),
            ("investment_details", InvestmentDetailSerializer, "investment_details"),
            ("withdrawal_details", WithdrawalDetailSerializer, "withdrawal_details"),
            ("reference_checks", ReferenceCheckSerializer, "reference_checks"),
            ("proof_of_address", ProofOfAddressSerializer, "proof_of_address"),
            ("insurance_verifications", InsuranceVerificationSerializer, "insurance_verifications"),
            ("driving_risk_assessments", DrivingRiskAssessmentSerializer, "driving_risk_assessments"),
            ("legal_work_eligibilities", LegalWorkEligibilitySerializer, "legal_work_eligibilities"),
            ("other_user_documents", OtherUserDocumentsSerializer, "other_user_documents"),
        ]
        nested_data = {field: validated_data.pop(field, []) for field, _, _ in nested_fields}

        image_fields = [
            ("profile_image", "profile_image_url"),
            ("drivers_licence_image1", "drivers_licence_image1_url"),
            ("drivers_licence_image2", "drivers_licence_image2_url"),
            ("Right_to_Work_file", "Right_to_Work_file_url"),
            ("Right_to_rent_file", "Right_to_rent_file_url"),
            ("dbs_certificate", "dbs_certificate_url"),
            ("dbs_update_file", "dbs_update_file_url"),
        ]
        for field, url_field in image_fields:
            file = validated_data.pop(field, None)
            if file and hasattr(file, "name"):
                # Check if file can be read
                try:
                    file.seek(0)
                    content = file.read(1)
                    file.seek(0)
                except Exception as read_e:
                    logger.error(f"File {field} cannot be read: {str(read_e)}")
                    raise serializers.ValidationError(f"File {field} is corrupted or cannot be read.")

                logger.info(f"Uploading {field}: {file.name}")
                try:
                    url = upload_file_dynamic(
                        file, file.name, content_type=getattr(file, "content_type", "application/octet-stream")
                    )
                    validated_data[url_field] = url
                    logger.info(f"{field} uploaded: {url}")
                except Exception as e:
                    logger.error(f"Failed to upload {field}: {str(e)}")
                    if "Expecting value" in str(e):
                        raise serializers.ValidationError(f"Failed to upload {field}. Server error occurred.")
                    else:
                        raise serializers.ValidationError(f"Failed to upload {field}. Please ensure the file is valid and try again.")
            else:
                logger.info(f"No file provided for {field}, setting {url_field} to None")
                validated_data[url_field] = None

        profile = super().create(validated_data)

        for field, serializer_class, related_name in nested_fields:
            items = nested_data[field]
            if items:
                serializer = serializer_class(data=items, many=True, context=self.context)
                if serializer.is_valid():
                    try:
                        serializer.save(user_profile=profile)
                        logger.info(f"Created {len(items)} {field} for profile {profile.id}")
                    except Exception as e:
                        logger.error(f"Failed to save {field} for profile {profile.id}: {str(e)}")
                        logger.error(f"Problematic data: {items}")
                        raise serializers.ValidationError(f"Failed to save {field}: {str(e)}")
                else:
                    logger.error(f"Validation failed for {field}: {serializer.errors}")
                    raise serializers.ValidationError({field: serializer.errors})
            else:
                logger.info(f"No {field} provided for profile {profile.id}")

        return profile

    def update(self, instance, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            instance.last_updated_by_id = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for update")

        logger.info(f"Updating UserProfile instance {instance.id} with validated data: {validated_data}")
        with transaction.atomic():
            nested_fields = [
                ("professional_qualifications", ProfessionalQualificationSerializer, "professional_qualifications"),
                ("employment_details", EmploymentDetailSerializer, "employment_details"),
                ("education_details", EducationDetailSerializer, "education_details"),
                ("skills", SkillDetailSerializer, "skill_details"),
                ("investment_details", InvestmentDetailSerializer, "investment_details"),
                ("withdrawal_details", WithdrawalDetailSerializer, "withdrawal_details"),
                ("reference_checks", ReferenceCheckSerializer, "reference_checks"),
                ("proof_of_address", ProofOfAddressSerializer, "proof_of_address"),
                ("insurance_verifications", InsuranceVerificationSerializer, "insurance_verifications"),
                ("driving_risk_assessments", DrivingRiskAssessmentSerializer, "driving_risk_assessments"),
                ("legal_work_eligibilities", LegalWorkEligibilitySerializer, "legal_work_eligibilities"),
                ("other_user_documents", OtherUserDocumentsSerializer, "other_user_documents"),
            ]
            nested_data = {field: validated_data.pop(field, None) for field, _, _ in nested_fields}

            image_fields = [
                ("profile_image", "profile_image_url"),
                ("drivers_licence_image1", "drivers_licence_image1_url"),
                ("drivers_licence_image2", "drivers_licence_image2_url"),
                ("Right_to_Work_file", "Right_to_Work_file_url"),
                ("Right_to_rent_file", "Right_to_rent_file_url"),
                ("dbs_certificate", "dbs_certificate_url"),
                ("dbs_update_file", "dbs_update_file_url"),
            ]
            for field, url_field in image_fields:
                file = validated_data.pop(field, None)
                if file and hasattr(file, "name"):
                    # Check if file can be read
                    try:
                        file.seek(0)
                        content = file.read(1)
                        file.seek(0)
                    except Exception as read_e:
                        logger.error(f"File {field} cannot be read: {str(read_e)}")
                        raise serializers.ValidationError(f"File {field} is corrupted or cannot be read.")

                    logger.info(f"Uploading {field}: {file.name}")
                    try:
                        url = upload_file_dynamic(
                            file, file.name, content_type=getattr(file, "content_type", "application/octet-stream")
                        )
                        validated_data[url_field] = url
                        logger.info(f"{field} uploaded: {url}")
                    except Exception as e:
                        logger.error(f"Failed to update {field}: {str(e)}")
                        if "Expecting value" in str(e):
                            raise serializers.ValidationError(f"Failed to upload {field}. Server error occurred.")
                        else:
                            raise serializers.ValidationError(f"Failed to upload {field}. Please ensure the file is valid and try again.")
                else:
                    logger.info(f"No file provided for {field}, keeping existing {url_field}")
                    validated_data[url_field] = getattr(instance, url_field, None)

            updated_instance = super().update(instance, validated_data)

            for field, serializer_class, related_name in nested_fields:
                items = nested_data[field]
                if items is not None:  # Only process if field is provided
                    existing_items = {item.id: item for item in getattr(updated_instance, related_name).all()}
                    sent_ids = set()

                    if items:  # Non-empty array
                        serializer = serializer_class(data=items, many=True, context=self.context)
                        if serializer.is_valid():
                            for item_data in items:
                                item_id = item_data.get("id")
                                if item_id and item_id in existing_items:
                                    # Update existing item
                                    item = existing_items[item_id]
                                    item_serializer = serializer_class(item, data=item_data, partial=True, context=self.context)
                                    if item_serializer.is_valid():
                                        item_serializer.save()
                                        logger.info(f"Updated {field} item {item_id} for profile {updated_instance.id}")
                                        sent_ids.add(item_id)
                                    else:
                                        logger.error(f"Validation failed for {field} item {item_id}: {item_serializer.errors}")
                                        raise serializers.ValidationError({field: item_serializer.errors})
                                else:
                                    # Try to find existing skill by name (for skills field)
                                    existing_item = None
                                    if field == "skills":
                                        existing_item = getattr(updated_instance, related_name).filter(skill_name=item_data.get("skill_name")).first()
                                    if existing_item:
                                        # Update existing
                                        item_serializer = serializer_class(existing_item, data=item_data, partial=True, context=self.context)
                                        if item_serializer.is_valid():
                                            item_serializer.save()
                                            logger.info(f"Updated existing {field} item {existing_item.id} for profile {updated_instance.id}")
                                            sent_ids.add(existing_item.id)
                                        else:
                                            logger.error(f"Validation failed for updating {field} item: {item_serializer.errors}")
                                            raise serializers.ValidationError({field: item_serializer.errors})
                                    else:
                                        # Create new item
                                        item_serializer = serializer_class(data=item_data, context=self.context)
                                        if item_serializer.is_valid():
                                            item_serializer.save(user_profile=updated_instance)
                                            logger.info(f"Created new {field} item for profile {updated_instance.id}")
                                        else:
                                            logger.error(f"Validation failed for new {field} item: {item_serializer.errors}")
                                            raise serializers.ValidationError({field: item_serializer.errors})
                        else:
                            logger.error(f"Validation failed for {field}: {serializer.errors}")
                            raise serializers.ValidationError({field: serializer.errors})

                        # Optionally delete items not included in the request
                        # for item_id in set(existing_items) - sent_ids:
                        #     existing_items[item_id].delete()
                        #     logger.info(f"Deleted {field} item {item_id} for profile {updated_instance.id}")
                    else:
                        logger.info(f"Empty {field} provided - no changes made")
                        # Optionally clear all items if an empty array is sent
                        # getattr(updated_instance, related_name).all().delete()
                        # logger.info(f"Cleared all {field} for profile {updated_instance.id}")
                else:
                    logger.info(f"No update for {field} - keeping existing")

            return updated_instance
        

class UserCreateSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(required=True)
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    is_superuser = serializers.BooleanField(default=False, required=False)
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)
    # last_updated_by = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "email",
            "password",
            "first_name",
            "last_name",
            "role",
            "status",
            "job_role",
            "is_superuser",
            "last_password_reset",
            "profile",
            "has_accepted_terms",
            "permission_levels",
            "manage_permission",
            "branch",
            # "last_updated_by_id",
            # "last_updated_by",
        ]
        read_only_fields = ["id", "last_password_reset"]
        extra_kwargs = {
            "email": {"required": True},
            "first_name": {"required": True},
            "last_name": {"required": True},
            "username": {"required": False, "allow_null": True},
            "role": {"required": False, "allow_null": True},
            "status": {"required": False, "allow_null": True},
            "job_role": {"required": False, "allow_null": True},
            "has_accepted_terms": {"required": False, "allow_null": True},
            "permission_levels": {"required": False, "allow_null": True},
        }


    def to_internal_value(self, data):
        logger.info(f"Raw payload in UserCreateSerializer: {dict(data)}")
        mutable_data = {}
        profile_data = {}

        if hasattr(data, "getlist"):
            # Initialize nested arrays
            nested_fields = [
                "professional_qualifications",
                "employment_details",
                "education_details",
                "skills",
                "investment_details",
                "withdrawal_details",
                "reference_checks",
                "proof_of_address",
                "insurance_verifications",
                "driving_risk_assessments",
                "legal_work_eligibilities",
                "other_user_documents",
            ]

            for field in nested_fields:
                profile_data[field] = []

            # Special handling for availability
            availability_data = {}
            for key in data:
                if key.startswith("profile[availability]"):
                    parts = key.split("[")
                    if len(parts) >= 4:
                        day = parts[2][:-1]  # monday, tuesday, etc.
                        if len(parts) == 4:  # profile[availability][day][available]
                            sub_field = parts[3][:-1]  # available
                            value = data.get(key)
                            if day not in availability_data:
                                availability_data[day] = {}
                            availability_data[day][sub_field] = value
                        elif len(parts) == 5:  # profile[availability][day][slot][field]
                            slot_index = int(parts[3][:-1])  # 0, 1, etc.
                            sub_field = parts[4][:-1]  # start, end, available
                            value = data.get(key)
                            if day not in availability_data:
                                availability_data[day] = []
                            while len(availability_data[day]) <= slot_index:
                                availability_data[day].append({})
                            availability_data[day][slot_index][sub_field] = value
            if availability_data:
                profile_data['availability'] = availability_data

            for key in data:
                # Handle both prefixed (profile[nested][0][field]) and non-prefixed (nested[0][field]) formats
                if key.startswith("profile[") and key.endswith("]") and not key.startswith("profile[availability]"):
                    # Handle profile-prefixed fields
                    if "][" in key:
                        parts = key.split("[")
                        field_name = parts[1][:-1]  # e.g., professional_qualifications

                        # Field name is already "skills"

                        index = int(parts[2][:-1])  # e.g., 0
                        sub_field = parts[3][:-1]  # e.g., image_file

                        # Ensure the list is long enough
                        while len(profile_data.get(field_name, [])) <= index:
                            profile_data[field_name].append({})

                        # Add value to the appropriate index
                        if key in self.context["request"].FILES:
                            profile_data[field_name][index][sub_field] = self.context["request"].FILES[key]
                        else:
                            profile_data[field_name][index][sub_field] = data.get(key)
                    else:
                        # Handle simple profile fields
                        field_name = key[len("profile[") : -1]
                        if key in self.context["request"].FILES:
                            profile_data[field_name] = self.context["request"].FILES[key]
                        else:
                            profile_data[field_name] = data.get(key)
                elif any(key.startswith(field + "[") for field in nested_fields) and "][" in key:
                    # Handle non-prefixed nested fields (e.g., professional_qualifications[0][name])
                    for field in nested_fields:
                        if key.startswith(field + "["):
                            parts = key.split("[")
                            index = int(parts[1][:-1])  # e.g., 0
                            sub_field = parts[2][:-1]  # e.g., name

                            # Ensure the list is long enough
                            while len(profile_data.get(field, [])) <= index:
                                profile_data[field].append({})

                            # Add value to the appropriate index
                            if key in self.context["request"].FILES:
                                profile_data[field][index][sub_field] = self.context["request"].FILES[key]
                            else:
                                profile_data[field][index][sub_field] = data.get(key)
                            break
                else:
                    mutable_data[key] = data.get(key)
        else:
            mutable_data = dict(data)
            profile_data = mutable_data.get("profile", {})

        logger.info(f"Parsed profile data: {profile_data}")
        mutable_data["profile"] = profile_data
        return super().to_internal_value(mutable_data)

    def create(self, validated_data):
        logger.info(f"Creating user with validated data: {validated_data}")
        profile_data = validated_data.pop("profile", {})
        is_superuser = validated_data.pop("is_superuser", False)
        branch = validated_data.pop("branch", None)
        tenant = self.context["request"].user.tenant
        password = validated_data.pop("password")

        with tenant_context(tenant):
            user = CustomUser.objects.create_user(
                **validated_data,
                tenant=tenant,
                branch=branch,
                is_superuser=is_superuser,
                is_staff=is_superuser,
                is_active=True,
                password=password,
            )

            user_data = get_user_data_from_jwt(self.context['request'])
            user_id = user_data.get('id')
            if user_id:
                user.last_updated_by_id = str(user_id)
                user.save()
            else:
                logger.warning("No user_id found in JWT payload for user creation")

            # Create profile using UserProfileSerializer - it will handle nested objects
            profile_serializer = UserProfileSerializer(data=profile_data, context=self.context)
            profile_serializer.is_valid(raise_exception=True)
            profile = profile_serializer.save(user=user)

            # Generate policy_number for investors
            if user.role == 'investor':
                policy_number = self._generate_policy_number(user)
                profile.policy_number = policy_number
                profile.save(update_fields=['policy_number'])
                logger.info(f"Assigned policy number {policy_number} to new investor {user.email}")

            return user

    def update(self, instance, validated_data):
        logger.info(f"Updating user {instance.email} with validated data: {validated_data}")
        with transaction.atomic():
            profile_data = validated_data.pop("profile", {})
            old_role = instance.role  # Capture old role before update

            # Update user fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            user_data = get_user_data_from_jwt(self.context['request'])
            user_id = user_data.get('id')
            if user_id:
                instance.last_updated_by_id = str(user_id)
                instance.save()
            else:
                logger.warning("No user_id found in JWT payload for user update")

            # Get or create profile
            profile = getattr(instance, "profile", None)
            if not profile:
                profile = UserProfile.objects.create(user=instance)

            # Update profile using UserProfileSerializer
            if profile_data:
                logger.info(f"Updating profile for user {instance.email} with data: {profile_data}")
                profile_serializer = UserProfileSerializer(
                    profile, data=profile_data, partial=True, context=self.context
                )
                profile_serializer.is_valid(raise_exception=True)
                profile_serializer.save()

            # New: Handle policy number based on role change
            new_role = instance.role
            if new_role == 'investor' and old_role != 'investor':
                if not profile.policy_number:
                    policy_number = self._generate_policy_number(instance)
                    profile.policy_number = policy_number
                    profile.save(update_fields=['policy_number'])
                    logger.info(f"Assigned policy number {policy_number} to investor {instance.email} on role change")
            elif old_role == 'investor' and new_role != 'investor':
                if profile.policy_number:
                    profile.policy_number = None
                    profile.save(update_fields=['policy_number'])
                    logger.info(f"Cleared policy number for non-investor {instance.email} on role change")

            return instance

    def _generate_policy_number(self, user):
        """Generate policy number: PREFIX-XXXXXX where PREFIX is first 3 letters of tenant name (upper), XXXXXX is 6-digit sequential per tenant."""
        tenant_name = user.tenant.name or 'APP'
        prefix = tenant_name[:3].upper()
        # Count existing investors in tenant (includes current user)
        count = CustomUser.objects.filter(tenant=user.tenant, role='investor').count()
        return f"{prefix}-{count:06d}"


class CustomUserListSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    tenant = serializers.SlugRelatedField(read_only=True, slug_field="name")
    branch = serializers.SlugRelatedField(read_only=True, slug_field="name", allow_null=True)
    permission_levels = serializers.ListField(child=serializers.CharField(), required=False)
    profile_completion_percentage = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "job_role",
            "tenant",
            "branch",
            "status",
            "permission_levels",
            "manage_permission",
            "profile",
            "profile_completion_percentage",
        ]  # Light fields

    def get_profile_completion_percentage(self, obj):
        try:
            return obj.calculate_completion_percentage()
        except Exception as e:
            logger.error(f"Error calculating profile completion for user {obj.email}: {str(e)}")
            return 0


class CustomUserSerializer(CustomUserListSerializer):
    profile = UserProfileSerializer(read_only=True)
    profile_completion_percentage = serializers.SerializerMethodField()
    two_factor_enabled = serializers.BooleanField(read_only=True)

    class Meta(CustomUserListSerializer.Meta):
        fields = "__all__"
        read_only_fields = ["id", "is_superuser", "last_password_reset", "is_locked", "login_attempts"]

    def get_profile_completion_percentage(self, obj):
        try:
            return obj.calculate_completion_percentage()
        except Exception as e:
            logger.error(f"Error calculating profile completion for user {obj.email}: {str(e)}")
            return 0


class UserAccountActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["lock", "unlock", "suspend", "activate"], required=True)

    def validate(self, data):
        user = self.context["user"]
        request = self.context["request"]
        if not (request.user.is_superuser or request.user.role == "admin"):
            raise serializers.ValidationError("Only admins or superusers can perform this action.")
        if user == request.user:
            raise serializers.ValidationError("You cannot perform this action on your own account.")
        return data


class UserPasswordRegenerateSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate(self, data):
        request = self.context["request"]
        if not (request.user.is_superuser or request.user.role == "admin"):
            raise serializers.ValidationError("Only admins or superusers can reset passwords.")
        email = data.get("email")
        with tenant_context(request.user.tenant):
            user = CustomUser.objects.filter(email=email).first()
            if not user:
                raise serializers.ValidationError("User with this email does not exist.")
            if user == request.user:
                raise serializers.ValidationError("You cannot reset your own password.")
        return data


class BlockedIPSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    blocked_by_email = serializers.EmailField(source="blocked_by.email", read_only=True)

    class Meta:
        model = BlockedIP
        fields = [
            "id",
            "ip_address",
            "tenant",
            "tenant_name",
            "reason",
            "blocked_at",
            "blocked_by",
            "blocked_by_email",
            "is_active",
        ]
        read_only_fields = ["id", "tenant_name", "blocked_at", "blocked_by_email"]

    def validate(self, data):
        request = self.context["request"]
        if not (request.user.is_superuser or request.user.role == "admin"):
            raise serializers.ValidationError("Only admins or superusers can manage blocked IPs.")
        ip_address = data.get("ip_address")
        tenant = data.get("tenant")
        with tenant_context(tenant):
            if (
                self.instance is None
                and BlockedIP.objects.filter(ip_address=ip_address, tenant=tenant, is_active=True).exists()
            ):
                raise serializers.ValidationError("This IP is already blocked for this tenant.")
        return data


class UserActivitySerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True, allow_null=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    global_correlation_id = serializers.UUIDField(read_only=True, required=False)
    
    performed_by_email = serializers.EmailField(source="performed_by.email", read_only=True, allow_null=True)

    class Meta:
        model = UserActivity
        fields = [
            "id",
            "user",
            "user_email",
            "tenant",
            "tenant_name",
            "action",
            "performed_by",
            'global_correlation_id',
            "performed_by_email",
            "timestamp",
            "details",
            "ip_address",
            "user_agent",
            "success",
        ]
        read_only_fields = [
            "id",
            "user_email",
            "tenant_name",
            "performed_by_email",
            "timestamp",
            "ip_address",
            "user_agent",
            "success",
        ]


class UserImpersonateSerializer(serializers.Serializer):
    def validate(self, data):
        request = self.context["request"]
        user = self.context["user"]
        if not request.user.is_superuser:
            raise serializers.ValidationError("Only superusers can impersonate users.")
        if user == request.user:
            raise serializers.ValidationError("You cannot impersonate your own account.")
        if user.is_locked or user.status == "suspended" or not user.is_active:
            raise serializers.ValidationError("Cannot impersonate a locked or suspended account.")
        return data


class AdminUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = CustomUser
        fields = "__all__"
        extra_kwargs = {
            "role": {"required": False, "default": "admin"},
            "email": {"required": True},
            "is_superuser": {"default": True},
            "is_staff": {"default": True},
        }

    def validate_email(self, value):
        try:
            domain = value.split("@")[1].lower()
        except IndexError:
            raise serializers.ValidationError("Invalid email format.")
        if not Domain.objects.filter(domain=domain).exists():
            raise serializers.ValidationError(f"No tenant found for domain '{domain}'.")
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError(f"User with email '{value}' already exists.")
        return value

    def create(self, validated_data):
        email = validated_data.pop("email")  # Pop email to avoid duplicate
        domain = email.split("@")[1].lower()
        domain_obj = Domain.objects.get(domain=domain)
        tenant = domain_obj.tenant
        password = validated_data.pop("password")
        validated_data["is_superuser"] = True
        validated_data["is_staff"] = True
        validated_data["role"] = validated_data.get("role", "admin")
        # Remove status and tenant from validated_data before creating user
        status = validated_data.pop("status", None)
        validated_data.pop("tenant", None)  # Remove tenant to avoid duplicate argument


        with tenant_context(tenant):
            user = CustomUser.objects.create_user(
                email=email,  # Explicitly pass email
                password=password,  # Pass password separately
                tenant=tenant,  # Explicitly pass tenant
                is_active=True,
                **validated_data,  # Unpack remaining validated_data
            )
            # Set status after user creation if needed
            if status is not None:
                user.status = status
            user.save()

            # Create UserProfile with all system access fields set to True
            UserProfile.objects.create(
                user=user,
                system_access_rostering=True,
                system_access_hr=True,
                system_access_recruitment=True,
                system_access_training=True,
                system_access_finance=True,
                system_access_compliance=True,
                system_access_co_superadmin=True,
                system_access_asset_management=True,
            )

            return user


class UserBranchUpdateSerializer(serializers.ModelSerializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = CustomUser
        fields = ["branch"]

    def validate_branch(self, value):
        if value is not None:
            tenant = self.context["request"].user.tenant
            with tenant_context(tenant):
                if not Branch.objects.filter(id=value.id, tenant=tenant).exists():
                    raise serializers.ValidationError(
                        f"Branch with ID {value.id} does not belong to tenant {tenant.schema_name}."
                    )
        return value

    def validate(self, data):
        tenant = self.context["request"].user.tenant
        user = self.instance
        if user.tenant != tenant:
            raise serializers.ValidationError("Cannot update branch for a user from a different tenant.")
        return data

    def update(self, instance, validated_data):
        instance.branch = validated_data.get("branch", instance.branch)
        instance.save()
        return instance


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    username = serializers.CharField(required=False)

    def validate(self, data):
        email = data.get('email')
        username = data.get('username')

        if not email and not username:
            raise serializers.ValidationError("Either 'email' or 'username' must be provided.")

        if email and username:
            raise serializers.ValidationError("Provide only one of 'email' or 'username', not both.")

        # NOTE: We can't validate existence here because we don't know the tenant yet
        # The tenant resolution happens in the view
        return data
    
class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True, write_only=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    username = serializers.CharField(required=False, allow_blank=True)
    new_password = serializers.CharField(
        write_only=True, 
        min_length=8, 
        required=True,
        style={'input_type': 'password'}
    )
    confirm_password = serializers.CharField(
        write_only=True, 
        required=True,
        style={'input_type': 'password'}
    )

    def validate(self, data):
        # Check if email or username is provided (optional but recommended)
        email = data.get('email')
        username = data.get('username')
        
        if not email and not username:
            # Allow token-only for backward compatibility
            logger.warning("Password reset confirmation without email/username (token-only)")
        
        # Check if passwords match
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        
        # Password complexity requirements
        password = data['new_password']
        if len(password) < 8:
            raise serializers.ValidationError({"new_password": "Password must be at least 8 characters long."})
        if not any(c.isupper() for c in password):
            raise serializers.ValidationError({"new_password": "Password must contain at least one uppercase letter."})
        if not any(c.isdigit() for c in password):
            raise serializers.ValidationError({"new_password": "Password must contain at least one number."})
            
        return data

    def validate_token(self, value):
        # Validate token format and optionally check if it exists
        # Note: Full validation happens in the view with tenant context
        try:
            uuid.UUID(value)
            return value
        except ValueError:
            raise serializers.ValidationError("Invalid token format.")
        
        
    
class UserSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSession
        fields = ["id", "login_time", "logout_time", "duration", "date", "ip_address", "user_agent"]


class ClientProfileSerializer(serializers.ModelSerializer):
    preferred_carers = serializers.PrimaryKeyRelatedField(
        many=True, queryset=CustomUser.objects.filter(role="carer"), required=False
    )
    photo = serializers.ImageField(required=False, allow_null=True, write_only=True)
    photo_url = serializers.CharField(max_length=1024, required=False, allow_blank=True, allow_null=True, read_only=True)
    last_updated_by = serializers.SerializerMethodField()

    class Meta:
        model = ClientProfile
        fields = "__all__"
        read_only_fields = ["id", "user", "client_id", "last_updated_by", "last_updated_by_id"]

    def get_last_updated_by(self, obj):
        return get_last_updated_by(self, obj)

    def validate(self, data):
        logger.info(f"Validating ClientProfileSerializer data: {data}")
        return super().validate(data)

    # def create(self, validated_data):
    #     user_data = get_user_data_from_jwt(self.context['request'])
    #     user_id = user_data.get('id')
    #     if user_id:
    #         validated_data['last_updated_by_id'] = str(user_id)
    #     else:
    #         logger.warning("No user_id found in JWT payload for creation")
    #         raise serializers.ValidationError({"last_updated_by_id": "User ID required for creation."})

    #     photo = validated_data.pop("photo", None)
    #     preferred_carers = validated_data.pop("preferred_carers", [])
    #     client_profile = super().create(validated_data)
    #     if photo and hasattr(photo, "name"):
    #         logger.info(f"Uploading client photo: {photo.name}")
    #         try:
    #             url = upload_file_dynamic(
    #                 photo, photo.name, content_type=getattr(photo, "content_type", "application/octet-stream")
    #             )
    #             client_profile.photo_url = url
    #             logger.info(f"Client photo uploaded: {url}")
    #         except Exception as e:
    #             logger.error(f"Failed to upload client photo: {str(e)}")
    #             raise serializers.ValidationError(f"Failed to upload photo: {str(e)}")
    #     else:
    #         logger.info("No photo provided for client profile, setting photo_url to None")
    #         client_profile.photo_url = None
    #     client_profile.preferred_carers.set(preferred_carers)
    #     client_profile.save()
    #     return client_profile




    def create(self, validated_data, **kwargs):
        user = kwargs.get('user')
        try:
            user_data = get_user_data_from_jwt(self.context['request'])
            user_id = user_data.get('id')

            if user_id:
                validated_data['last_updated_by_id'] = str(user_id)
            else:
                logger.warning("No user_id found in JWT payload for client creation")
                # Instead of raising an error, use a fallback or leave it null
                # You might want to use the authenticated user's ID instead
                if self.context['request'].user.is_authenticated:
                    validated_data['last_updated_by_id'] = str(self.context['request'].user.id)
                else:
                    logger.warning("No authenticated user found, setting last_updated_by_id to None")
                    validated_data['last_updated_by_id'] = None

        except Exception as e:
            logger.error(f"Error extracting user data from JWT: {str(e)}")
            # Fallback to authenticated user if available
            if self.context['request'].user.is_authenticated:
                validated_data['last_updated_by_id'] = str(self.context['request'].user.id)
            else:
                validated_data['last_updated_by_id'] = None

        # Set the user for creation since it's required
        if user:
            validated_data['user'] = user

        # Rest of your existing code for photo upload and creation
        photo = validated_data.pop("photo", None)
        preferred_carers = validated_data.pop("preferred_carers", [])
        client_profile = super().create(validated_data)

        if photo and hasattr(photo, "name"):
            logger.info(f"Uploading client photo: {photo.name}")
            try:
                url = upload_file_dynamic(
                    photo, photo.name, content_type=getattr(photo, "content_type", "application/octet-stream")
                )
                client_profile.photo_url = url
                logger.info(f"Client photo uploaded: {url}")
            except Exception as e:
                logger.error(f"Failed to upload client photo: {str(e)}")
                # Don't raise error here, just log it
        else:
            logger.info("No photo provided for client profile, setting photo_url to None")
            client_profile.photo_url = None

        client_profile.preferred_carers.set(preferred_carers)
        client_profile.save()
        return client_profile



    def update(self, instance, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            instance.last_updated_by_id = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for update")

        photo = validated_data.pop("photo", None)
        preferred_carers = validated_data.pop("preferred_carers", None)
        instance = super().update(instance, validated_data)
        if photo and hasattr(photo, "name"):
            logger.info(f"Updating client photo: {photo.name}")
            try:
                url = upload_file_dynamic(
                    photo, photo.name, content_type=getattr(photo, "content_type", "application/octet-stream")
                )
                instance.photo_url = url
                logger.info(f"Client photo updated: {url}")
            except Exception as e:
                logger.error(f"Failed to update client photo: {str(e)}")
                raise serializers.ValidationError(f"Failed to update photo: {str(e)}")
        elif photo is None:
            logger.info("No photo provided for update, keeping existing photo_url")
            instance.photo_url = getattr(instance, "photo_url", None)
        if preferred_carers is not None:
            instance.preferred_carers.set(preferred_carers)
        instance.save()
        return instance


class ClientDetailSerializer(serializers.ModelSerializer):
    profile = ClientProfileSerializer()

    class Meta:
        model = CustomUser
        fields = ["id", "email", "first_name", "last_name", "role", "username", "job_role", "branch", "profile"]
        read_only_fields = ["id", "role"]

    def to_internal_value(self, data):
        """
        Custom parsing for multipart/form-data to handle nested 'profile' fields and files.
        Supports both simple nested (e.g., profile[photo]) and deeper nested (e.g., profile[preferred_carers][0]).
        """
        logger.info(f"Raw payload in ClientDetailSerializer: {dict(data) if hasattr(data, 'dict') else data}")
        mutable_data = {}
        profile_data = {}

        if hasattr(data, "getlist"):  # Multipart/form-data case
            # Initialize nested arrays (e.g., preferred_carers)
            nested_arrays = ["preferred_carers"]  # Add more if needed (e.g., for future many=True fields)
            for field in nested_arrays:
                profile_data[field] = []

            for key in data:
                if key.startswith("profile[") and key.endswith("]"):
                    # Handle profile-prefixed fields
                    if "][" in key:
                        # Deeper nested: e.g., profile[preferred_carers][0]
                        parts = key.split("[")
                        field_name = parts[1][:-1]  # e.g., "preferred_carers"
                        index_str = parts[2][:-1]   # e.g., "0"
                        if len(parts) > 3:
                            sub_field = parts[3][:-1]  # e.g., sub-sub-field
                            index = int(index_str)

                            # Ensure list is long enough
                            while len(profile_data.get(field_name, [])) <= index:
                                profile_data[field_name].append({})

                            # Add value (file or text)
                            if key in self.context["request"].FILES:
                                profile_data[field_name][index][sub_field] = self.context["request"].FILES[key]
                            else:
                                profile_data[field_name][index][sub_field] = data.get(key)
                        else:
                            # Handle edge cases if needed
                            pass
                    else:
                        # Simple nested: e.g., profile[photo]
                        field_name = key[len("profile[") : -1]
                        if key in self.context["request"].FILES:
                            profile_data[field_name] = self.context["request"].FILES[key]
                        else:
                            profile_data[field_name] = data.get(key)
                else:
                    # Top-level fields (e.g., email, first_name)
                    mutable_data[key] = data.get(key)
        else:
            # JSON case (no files)
            mutable_data = dict(data)
            profile_data = mutable_data.get("profile", {})

        logger.info(f"Parsed profile data: {profile_data}")
        mutable_data["profile"] = profile_data
        return super().to_internal_value(mutable_data)

    def to_representation(self, instance):
        """
        FIXED: Safely check for client_profile existence to avoid RelatedObjectDoesNotExist error
        """
        data = super().to_representation(instance)
        
        # Safe check using hasattr() or try-except
        try:
            if hasattr(instance, 'client_profile') and instance.client_profile:
                data["profile"] = ClientProfileSerializer(instance.client_profile).data
            else:
                data["profile"] = None
        except ClientProfile.DoesNotExist:
            # This exception is raised when accessing instance.client_profile on a user without one
            data["profile"] = None
            logger.warning(f"User {instance.email} does not have a client_profile")
        
        return data

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", {})
        instance = super().update(instance, validated_data)

        # Safe check before updating profile
        try:
            if hasattr(instance, 'client_profile') and instance.client_profile:
                profile_serializer = ClientProfileSerializer(
                    instance.client_profile, 
                    data=profile_data, 
                    partial=True, 
                    context=self.context
                )
                profile_serializer.is_valid(raise_exception=True)
                profile_serializer.save()
        except ClientProfile.DoesNotExist:
            logger.warning(f"Cannot update client_profile for user {instance.email} - profile does not exist")
        
        return instance

        
class ClientCreateSerializer(serializers.ModelSerializer):
    profile = ClientProfileSerializer(required=True)
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)
    # last_updated_by = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ["id", "username", "email", "password", "first_name", "last_name", "role", "job_role", "profile", "branch", "status"]
        read_only_fields = ["id", "username"]
        extra_kwargs = {
            "email": {"required": True},
            "first_name": {"required": True},
            "last_name": {"required": True},
            "status": {"required": False},
            "role": {"default": "client"},
        }

    def get_last_updated_by(self, obj):
        return get_last_updated_by(self, obj)

    def create(self, validated_data):
        profile_data = validated_data.pop("profile")
        branch = validated_data.pop("branch", None)
        tenant = self.context["request"].user.tenant
        password = validated_data.pop("password")

        # Handle JSON fields
        for field in ["order_history", "payment_history", "feedback", "complaints", "preferred_care_times"]:
            if field in profile_data and isinstance(profile_data[field], str):
                import json
                try:
                    profile_data[field] = json.loads(profile_data[field])
                except Exception:
                    profile_data[field] = {}

        with tenant_context(tenant):
            user = CustomUser.objects.create_user(
                **validated_data, tenant=tenant, branch=branch, is_active=True, password=password
            )

            user_data = get_user_data_from_jwt(self.context['request'])
            user_id = user_data.get('id')
            if user_id:
                user.last_updated_by_id = str(user_id)
                user.save()
            else:
                logger.warning("No user_id found in JWT payload for user creation")

            # Use serializer for upload handling
            profile_serializer = ClientProfileSerializer(data=profile_data, context=self.context)
            profile_serializer.is_valid(raise_exception=True)
            profile_serializer.save(user=user)
            return user

    
    def to_representation(self, instance):
        """
        Include the profile data in the response when creating a client.
        """
        representation = super().to_representation(instance)
        
        # Add profile data to the response
        try:
            if hasattr(instance, 'client_profile') and instance.client_profile:
                representation['profile'] = ClientProfileSerializer(instance.client_profile).data
            else:
                representation['profile'] = None
        except ClientProfile.DoesNotExist:
            representation['profile'] = None
            
        return representation


class DocumentPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentPermission
        fields = ["user_id", "email", "first_name", "last_name", "role", "permission_level", "created_at"]
        read_only_fields = ["created_at"]


class DocumentPermissionWriteSerializer(serializers.Serializer):
    user_id = serializers.CharField(max_length=255, required=False, allow_blank=False)
    email = serializers.EmailField(required=False, allow_blank=False)
    permission_level = serializers.ChoiceField(choices=DocumentPermission.PERMISSION_CHOICES, required=False)


class DocumentVersionSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = DocumentVersion
        fields = ['version', 'file_url', 'file_path', 'file_type', 'file_size', 'created_at', 'created_by']
        read_only_fields = ['version', 'file_url', 'file_path', 'file_type', 'file_size', 'created_at', 'created_by']

    @extend_schema_field(
        {
            "type": "object",
            "properties": {
                "email": {"type": "string"},
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "job_role": {"type": "string"},
            },
        }
    )
    def get_created_by(self, obj):
        if obj.created_by_id:
            try:
                user = CustomUser.objects.get(id=obj.created_by_id)
                return {
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "job_role": getattr(user.profile, 'job_role', '') if hasattr(user, 'profile') else '',
                }
            except CustomUser.DoesNotExist:
                logger.error(f"User {obj.created_by_id} not found")
                return None
        return None

class DocumentAcknowledgmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentAcknowledgment
        fields = ["id", "document", "user_id", "email", "first_name", "last_name", "role", "acknowledged_at", "tenant_id"]
        read_only_fields = ["id", "document", "user_id", "email", "first_name", "last_name", "role", "acknowledged_at", "tenant_id"]

class DocumentPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentPermission
        fields = ["user_id", "email", "first_name", "last_name", "role", "permission_level", "created_at"]
        read_only_fields = ["created_at"]


class DocumentSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    uploaded_by = serializers.SerializerMethodField()
    updated_by = serializers.SerializerMethodField()
    last_updated_by = serializers.SerializerMethodField()
    tenant_domain = serializers.SerializerMethodField()
    acknowledgments = DocumentAcknowledgmentSerializer(many=True, read_only=True)
    permissions = DocumentPermissionSerializer(many=True, read_only=True)
    permissions_write = DocumentPermissionWriteSerializer(many=True, required=False, write_only=True)
    permission_action = serializers.ChoiceField(choices=['add', 'remove', 'replace', 'update_level'], required=False, write_only=True)
    file = serializers.FileField(required=False, allow_null=True)



    def to_internal_value(self, data):
        # data is Immutable QueryDict in multipart → make it mutable
        mutable_data = data.copy()

        # Remove id completely so DRF never sees it
        mutable_data.pop('id', None)

        # Flatten single-item lists (file, title, etc. come as lists in multipart)
        # But exclude permissions_write which should remain as a list
        for key, value in mutable_data.items():
            if key != 'permissions_write' and isinstance(value, list) and len(value) == 1:
                mutable_data[key] = value[0]

        # Parse permissions_write from multipart
        permissions_write_data = []
        i = 0
        while True:
            user_id_key = f'permissions_write[{i}][user_id]'
            if user_id_key not in data:
                break
            perm = {
                'user_id': data.get(user_id_key),
                'email': data.get(f'permissions_write[{i}][email]'),
                'permission_level': data.get(f'permissions_write[{i}][permission_level]'),
            }
            permissions_write_data.append(perm)
            i += 1
        if permissions_write_data:
            mutable_data['permissions_write'] = permissions_write_data

        ret = super().to_internal_value(mutable_data)
        return ret


    class Meta:
        model = Document
        fields = [
            "id",
            "tenant_id",
            "tenant_domain",
            "title",
            "description",
            "file_url",
            "file_path",
            "file_type",
            "file_size",
            "version",
            "uploaded_by_id",
            "uploaded_by",
            "updated_by_id",
            "updated_by",
            "last_updated_by_id",
            "last_updated_by",
            "uploaded_at",
            "updated_at",
            "expiring_date",
            "status",
            "document_number",
            "tags",
            "file",
            "acknowledgments",
            "permissions",
            "permissions_write",
            "permission_action",
        ]
        read_only_fields = [
            "id",
            "tenant_id",
            "tenant_domain",
            "uploaded_by_id",
            "updated_by_id",
            "last_updated_by_id",
            "uploaded_at",
            "updated_at",
            "document_number",
            "file_url",
            "file_path",
            "version",
            "last_updated_by",
            "acknowledgments",
            "permissions",
        ]

    @extend_schema_field(
        {
            "type": "object",
            "properties": {
                "email": {"type": "string"},
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "job_role": {"type": "string"},
            },
        }
    )
    def get_uploaded_by(self, obj):
        if obj.uploaded_by_id:
            try:
                user = CustomUser.objects.get(id=obj.uploaded_by_id)
                return {
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "job_role": getattr(user.profile, 'job_role', '') if hasattr(user, 'profile') else '',
                }
            except CustomUser.DoesNotExist:
                logger.warning(f"User {obj.uploaded_by_id} not found")
                return None
        return None

    @extend_schema_field(
        {
            "type": "object",
            "properties": {
                "email": {"type": "string"},
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "job_role": {"type": "string"},
            },
        }
    )
    def get_updated_by(self, obj):
        if obj.updated_by_id:
            try:
                user = CustomUser.objects.get(id=obj.updated_by_id)
                return {
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "job_role": getattr(user.profile, 'job_role', '') if hasattr(user, 'profile') else '',
                }
            except CustomUser.DoesNotExist:
                logger.warning(f"User {obj.updated_by_id} not found")
                return None
        return None

    def get_last_updated_by(self, obj):
        return get_last_updated_by(self, obj)  # Assuming this function exists

    @extend_schema_field(str)
    def get_tenant_domain(self, obj):
        try:
            if isinstance(obj.tenant_id, int):
                # tenant_id is already the integer ID
                domain = Domain.objects.filter(tenant_id=obj.tenant_id, is_primary=True).first()
            else:
                # tenant_id is a UUID string, resolve to tenant integer ID
                tenant = Tenant.objects.get(unique_id=obj.tenant_id)
                domain = Domain.objects.filter(tenant_id=tenant.id, is_primary=True).first()
            return domain.domain if domain else None
        except Exception as e:
            logger.error(f"Error fetching tenant domain for {obj.tenant_id}: {str(e)}")
            return None

    def validate_file(self, value):
        if value:
            if not value.name.lower().endswith((".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx")):
                raise serializers.ValidationError("Only PDF, image, or Word document files are allowed.")
            if value.size > 10 * 1024 * 1024:  # 10MB limit
                raise serializers.ValidationError("File size cannot exceed 10MB.")
        return value

    def validate_permissions_write(self, value):
            if value:
                valid_levels = [choice[0] for choice in DocumentPermission.PERMISSION_CHOICES]
                for perm_data in value:
                    if 'permission_level' in perm_data and perm_data['permission_level'] not in valid_levels:
                        raise serializers.ValidationError("Invalid permission_level. Must be 'view' or 'view_download'.")
                    if ('user_id' not in perm_data or not perm_data['user_id']) and ('email' not in perm_data or not perm_data['email']):
                        raise serializers.ValidationError("Each permission must include either 'user_id' or 'email'.")
                    if ('user_id' in perm_data and perm_data['user_id']) and ('email' in perm_data and perm_data['email']):
                        raise serializers.ValidationError("Each permission must include exactly one of 'user_id' or 'email', not both.")
            return value


    def validate(self, data):
        tenant_id = get_tenant_id_from_jwt(self.context["request"])
        # Note: tenant_id is read-only and set in create/update methods
        # Validate uploaded_by_id and updated_by_id if provided
        if "uploaded_by_id" in data:
            try:
                # Try numeric ID first, fallback will be handled by exceptions
                user = CustomUser.objects.get(id=int(data["uploaded_by_id"]))
                user_tenant_uuid = str(Tenant.objects.get(id=user.tenant_id).unique_id)
                if user_tenant_uuid != str(tenant_id):
                    raise serializers.ValidationError({"uploaded_by_id": "User does not belong to this tenant."})
            except (CustomUser.DoesNotExist, Tenant.DoesNotExist, ValueError):
                # ValueError can happen if a non-numeric value (e.g., UUID) was passed for an integer PK
                raise serializers.ValidationError({"uploaded_by_id": "Invalid user ID."})
        if "updated_by_id" in data:
            try:
                user = CustomUser.objects.get(id=int(data["updated_by_id"]))
                user_tenant_uuid = str(Tenant.objects.get(id=user.tenant_id).unique_id)
                if user_tenant_uuid != str(tenant_id):
                    raise serializers.ValidationError({"updated_by_id": "User does not belong to this tenant."})
            except (CustomUser.DoesNotExist, Tenant.DoesNotExist, ValueError):
                raise serializers.ValidationError({"updated_by_id": "Invalid user ID."})
        # Validate permissions_write users belong to tenant
        permissions_write = data.get('permissions_write', [])
        permission_action = data.get('permission_action', 'add')
        resolved_permissions = []
        for perm_data in permissions_write:
            if permission_action == 'remove':
                user = None
                if 'user_id' in perm_data and perm_data['user_id']:
                    try:
                        user_id = int(perm_data['user_id'])
                        user = CustomUser.objects.get(id=user_id)
                    except (CustomUser.DoesNotExist, ValueError):
                        raise serializers.ValidationError({"permissions_write": f"Invalid user ID: {perm_data['user_id']}"})
                elif 'email' in perm_data and perm_data['email']:
                    try:
                        user = CustomUser.objects.get(email=perm_data['email'])
                    except CustomUser.DoesNotExist:
                        raise serializers.ValidationError({"permissions_write": f"Invalid user email: {perm_data['email']}"})
                if not user:
                    raise serializers.ValidationError({"permissions_write": "Could not resolve user from provided ID or email."})
                try:
                    user_tenant_uuid = str(Tenant.objects.get(id=user.tenant_id).unique_id)
                    if user_tenant_uuid != str(tenant_id):
                        raise serializers.ValidationError({"permissions_write": f"User {perm_data.get('user_id', perm_data.get('email'))} does not belong to this tenant."})
                except Tenant.DoesNotExist:
                    raise serializers.ValidationError({"permissions_write": f"Invalid tenant for user {perm_data.get('user_id', perm_data.get('email'))}."})
                resolved_perm = {'resolved_user_id': str(user.id)}
                resolved_permissions.append(resolved_perm)
            else:  # add, replace, update_level
                user = None
                if 'user_id' in perm_data and perm_data['user_id']:
                    try:
                        user_id = int(perm_data['user_id'])
                        user = CustomUser.objects.get(id=user_id)
                    except (CustomUser.DoesNotExist, ValueError):
                        raise serializers.ValidationError({"permissions_write": f"Invalid user ID: {perm_data['user_id']}"})
                elif 'email' in perm_data and perm_data['email']:
                    try:
                        user = CustomUser.objects.get(email=perm_data['email'])
                    except CustomUser.DoesNotExist:
                        raise serializers.ValidationError({"permissions_write": f"Invalid user email: {perm_data['email']}"})
                if not user:
                    raise serializers.ValidationError({"permissions_write": "Could not resolve user from provided ID or email."})
                try:
                    user_tenant_uuid = str(Tenant.objects.get(id=user.tenant_id).unique_id)
                    if user_tenant_uuid != str(tenant_id):
                        raise serializers.ValidationError({"permissions_write": f"User {perm_data.get('user_id', perm_data.get('email'))} does not belong to this tenant."})
                except Tenant.DoesNotExist:
                    raise serializers.ValidationError({"permissions_write": f"Invalid tenant for user {perm_data.get('user_id', perm_data.get('email'))}."})
                resolved_perm = {
                    'resolved_user_id': str(user.id),
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': getattr(user.profile, 'job_role', '') if hasattr(user, 'profile') else '',
                    'permission_level': perm_data.get('permission_level', 'view_download')
                }
                resolved_permissions.append(resolved_perm)
        data['resolved_permissions_write'] = resolved_permissions
        data['permission_action'] = permission_action
        return data



    def create(self, validated_data):
        resolved_permissions = validated_data.pop("resolved_permissions_write", [])
        permissions_write = validated_data.pop("permissions_write", [])
        permission_action = validated_data.pop("permission_action", "add")
        file = validated_data.pop("file", None)
        current_user = get_user_data_from_jwt(self.context["request"])
        auth_header = self.context["request"].headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise serializers.ValidationError("No valid Bearer token provided.")
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            tenant_unique_id = payload.get("tenant_unique_id")
        except Exception as e:
            logger.error(f"Invalid JWT token: {str(e)}")
            raise serializers.ValidationError("Invalid JWT token.")
        tenant = Tenant.objects.get(unique_id=tenant_unique_id)
        validated_data["tenant_id"] = str(tenant.id)
        validated_data["uploaded_by_id"] = str(current_user["id"])
        validated_data["updated_by_id"] = str(current_user["id"])
        validated_data["last_updated_by_id"] = str(current_user["id"])
        # Ensure 'id' is not in validated_data
        validated_data.pop('id', None)

        if file:
            logger.info(f"Uploading document file: {file.name}")
            file_name = f"{file.name.rsplit('.', 1)[0]}_v1.{file.name.rsplit('.', 1)[1]}" if '.' in file.name else f"{file.name}_v1"
            url = upload_file_dynamic(
                file, file_name, content_type=getattr(file, "content_type", "application/octet-stream")
            )
            validated_data["file_url"] = url
            validated_data["file_path"] = url
            validated_data["file_type"] = getattr(file, "content_type", "application/octet-stream")
            validated_data["file_size"] = file.size
            logger.info(f"Document file uploaded: {url}")

        document = super().create(validated_data)
        tenant_id = str(tenant.unique_id)
        if file:
            DocumentVersion.objects.create(
                document=document,
                version=1,
                file_url=validated_data["file_url"],
                file_path=validated_data["file_path"],
                file_type=validated_data["file_type"],
                file_size=validated_data["file_size"],
                created_by_id=validated_data["uploaded_by_id"],
            )
        
        # Automatically grant full access to creator
        try:
            # First try numeric ID lookup (common case). If that fails due to non-numeric value,
            # fall back to resolving by email from the token payload to avoid a 500 error.
            creator = None
            creator_id_val = validated_data.get("uploaded_by_id")
            try:
                creator = CustomUser.objects.get(id=int(creator_id_val))
            except (ValueError, TypeError, CustomUser.DoesNotExist):
                # Fallback: try to resolve by email from current_user payload
                try:
                    creator = CustomUser.objects.get(email=current_user.get("email"))
                except CustomUser.DoesNotExist:
                    creator = None

            if creator:
                creator_permission = DocumentPermission(
                    document=document,
                    user_id=str(creator.id),
                    email=creator.email,
                    first_name=creator.first_name,
                    last_name=creator.last_name,
                    role=getattr(creator.profile, 'job_role', '') if hasattr(creator, 'profile') else '',
                    permission_level='view_download',
                    tenant_id=tenant_id
                )
                creator_permission.save()
                logger.info(f"Automatically granted full access to creator {creator.email} for document {document.title}")
            else:
                logger.error(f"Creator user {validated_data.get('uploaded_by_id')} not found or could not be resolved")
        except Exception as e:
            logger.error(f"Error granting creator permission: {str(e)}")
        
        # Handle additional permissions
        if resolved_permissions:
            if permission_action == 'add':
                permission_objs = [
                    DocumentPermission(
                        document=document,
                        user_id=perm['resolved_user_id'],
                        email=perm['email'],
                        first_name=perm['first_name'],
                        last_name=perm['last_name'],
                        role=perm['role'],
                        permission_level=perm['permission_level'],
                        tenant_id=tenant_id
                    )
                    for perm in resolved_permissions
                ]
                DocumentPermission.objects.bulk_create(permission_objs)
                logger.info(f"Added {len(resolved_permissions)} permissions for document {document.title}")
            elif permission_action == 'replace':
                permission_objs = [
                    DocumentPermission(
                        document=document,
                        user_id=perm['resolved_user_id'],
                        email=perm['email'],
                        first_name=perm['first_name'],
                        last_name=perm['last_name'],
                        role=perm['role'],
                        permission_level=perm['permission_level'],
                        tenant_id=tenant_id
                    )
                    for perm in resolved_permissions
                ]
                DocumentPermission.objects.bulk_create(permission_objs)
                logger.info(f"Replaced (added) {len(resolved_permissions)} permissions for document {document.title}")

        return document

    # def update(self, instance, validated_data):
    #     resolved_permissions = validated_data.pop("resolved_permissions_write", None)
    #     permissions_write = validated_data.pop("permissions_write", None)
    #     permission_action = validated_data.pop("permission_action", "add")
    #     file = validated_data.pop("file", None)
    #     current_user = get_user_data_from_jwt(self.context["request"])
    #     validated_data["updated_by_id"] = str(current_user["id"])
    #     instance.last_updated_by_id = str(current_user["id"])
    #     tenant_id = instance.tenant_id

    #     with transaction.atomic():
    #         if file:
    #             DocumentVersion.objects.create(
    #                 document=instance,
    #                 version=instance.version,
    #                 file_url=instance.file_url,
    #                 file_path=instance.file_path,
    #                 file_type=instance.file_type,
    #                 file_size=instance.file_size,
    #                 created_by_id=instance.updated_by_id or instance.uploaded_by_id,
    #             )
    #             instance.version += 1
    #             validated_data["version"] = instance.version
    #             file_name = f"{file.name.rsplit('.', 1)[0]}_v{instance.version}.{file.name.rsplit('.', 1)[1]}" if '.' in file.name else f"{file.name}_v{instance.version}"
    #             url = upload_file_dynamic(
    #                 file, file_name, content_type=getattr(file, "content_type", "application/octet-stream")
    #             )
    #             validated_data["file_url"] = url
    #             validated_data["file_path"] = url
    #             validated_data["file_type"] = getattr(file, "content_type", "application/octet-stream")
    #             validated_data["file_size"] = file.size
    #             logger.info(f"Document file updated: {url}")

    #         instance = super().update(instance, validated_data)
    #         if file:
    #             DocumentVersion.objects.create(
    #                 document=instance,
    #                 version=instance.version,
    #                 file_url=validated_data["file_url"],
    #                 file_path=validated_data["file_path"],
    #                 file_type=validated_data["file_type"],
    #                 file_size=validated_data["file_size"],
    #                 created_by_id=validated_data["updated_by_id"],
    #             )
            
    #         if permissions_write is not None:
    #             existing_permissions = instance.permissions.filter(tenant_id=tenant_id)
    #             if permission_action == 'add':
    #                 added_count = 0
    #                 for perm in resolved_permissions:
    #                     if not existing_permissions.filter(user_id=perm['resolved_user_id']).exists():
    #                         new_perm = DocumentPermission(
    #                             document=instance,
    #                             user_id=perm['resolved_user_id'],
    #                             email=perm['email'],
    #                             first_name=perm['first_name'],
    #                             last_name=perm['last_name'],
    #                             role=perm['role'],
    #                             permission_level=perm['permission_level'],
    #                             tenant_id=tenant_id
    #                         )
    #                         new_perm.save()
    #                         added_count += 1
    #                 logger.info(f"Added {added_count} new permissions for document {instance.title}")
    #             elif permission_action == 'remove':
    #                 removed_count = 0
    #                 for perm in resolved_permissions:
    #                     deleted = existing_permissions.filter(user_id=perm['resolved_user_id']).delete()[0]
    #                     removed_count += deleted
    #                 logger.info(f"Removed {removed_count} permissions for document {instance.title}")
    #             elif permission_action == 'replace':
    #                 existing_permissions.delete()
    #                 permission_objs = [
    #                     DocumentPermission(
    #                         document=instance,
    #                         user_id=perm['resolved_user_id'],
    #                         email=perm['email'],
    #                         first_name=perm['first_name'],
    #                         last_name=perm['last_name'],
    #                         role=perm['role'],
    #                         permission_level=perm['permission_level'],
    #                         tenant_id=tenant_id
    #                     )
    #                     for perm in resolved_permissions
    #                 ]
    #                 DocumentPermission.objects.bulk_create(permission_objs)
    #                 logger.info(f"Replaced with {len(resolved_permissions)} permissions for document {instance.title}")
        
    #     return instance

    def update(self, instance, validated_data):
        resolved_permissions = validated_data.pop("resolved_permissions_write", None)
        permissions_write = validated_data.pop("permissions_write", None)
        permission_action = validated_data.pop("permission_action", "add")
        file = validated_data.pop("file", None)
        current_user = get_user_data_from_jwt(self.context["request"])
        validated_data["updated_by_id"] = str(current_user["id"])
        instance.last_updated_by_id = str(current_user["id"])
        # Get the tenant from the instance's tenant_id (id string)
        tenant = Tenant.objects.get(id=int(instance.tenant_id))
        tenant_id = str(tenant.id)
        # Update instance tenant_id to id string for consistency
        instance.tenant_id = str(tenant.id)

        with transaction.atomic():
            # Store the old file info BEFORE updating
            old_file_info = {
                'file_url': instance.file_url,
                'file_path': instance.file_path,
                'file_type': instance.file_type,
                'file_size': instance.file_size,
                'version': instance.version
            }

            if file:
                # Only create version history if there was a previous file AND it's different from the new one
                if instance.file_url and instance.file_url != old_file_info['file_url']:
                    # Check if version already exists before creating
                    if not DocumentVersion.objects.filter(document=instance, version=old_file_info['version']).exists():
                        DocumentVersion.objects.create(
                            document=instance,
                            version=old_file_info['version'],
                            file_url=old_file_info['file_url'],
                            file_path=old_file_info['file_path'],
                            file_type=old_file_info['file_type'],
                            file_size=old_file_info['file_size'],
                            created_by_id=instance.updated_by_id or instance.uploaded_by_id,
                        )
                
                # Increment version for the new file
                instance.version += 1
                validated_data["version"] = instance.version
                
                # Upload new file
                file_name = f"{file.name.rsplit('.', 1)[0]}_v{instance.version}.{file.name.rsplit('.', 1)[1]}" if '.' in file.name else f"{file.name}_v{instance.version}"
                url = upload_file_dynamic(
                    file, file_name, content_type=getattr(file, "content_type", "application/octet-stream")
                )
                validated_data["file_url"] = url
                validated_data["file_path"] = url
                validated_data["file_type"] = getattr(file, "content_type", "application/octet-stream")
                validated_data["file_size"] = file.size
                logger.info(f"Document file updated: {url}")

            # Update the document instance
            instance = super().update(instance, validated_data)

            # Create DocumentVersion for the NEW file (only if file was updated and version doesn't exist)
            if file:
                # Check if this version already exists before creating
                if not DocumentVersion.objects.filter(document=instance, version=instance.version).exists():
                    DocumentVersion.objects.create(
                        document=instance,
                        version=instance.version,
                        file_url=validated_data["file_url"],
                        file_path=validated_data["file_path"],
                        file_type=validated_data["file_type"],
                        file_size=validated_data["file_size"],
                        created_by_id=validated_data["updated_by_id"],
                    )
                else:
                    logger.warning(f"DocumentVersion for document {instance.id} version {instance.version} already exists, skipping creation")
            
            # Handle permissions (your existing code)
            if permissions_write is not None:
                existing_permissions = instance.permissions.filter(tenant_id=tenant_id)
                if permission_action == 'add':
                    added_count = 0
                    for perm in resolved_permissions:
                        obj, created = DocumentPermission.objects.update_or_create(
                            document=instance,
                            user_id=str(perm['resolved_user_id']),
                            tenant_id=str(tenant_id),
                            defaults={
                                'email': perm['email'],
                                'first_name': perm['first_name'],
                                'last_name': perm['last_name'],
                                'role': perm['role'],
                                'permission_level': perm['permission_level'],
                            }
                        )
                        if created:
                            added_count += 1
                    logger.info(f"Added or updated {added_count} permissions for document {instance.title}")
                elif permission_action == 'remove':
                    removed_count = 0
                    for perm in resolved_permissions:
                        deleted = existing_permissions.filter(user_id=perm['resolved_user_id']).delete()[0]
                        removed_count += deleted
                    logger.info(f"Removed {removed_count} permissions for document {instance.title}")
                elif permission_action == 'replace':
                    existing_permissions.delete()
                    replaced_count = 0
                    for perm in resolved_permissions:
                        obj, created = DocumentPermission.objects.update_or_create(
                            document=instance,
                            user_id=str(perm['resolved_user_id']),
                            tenant_id=str(tenant_id),
                            defaults={
                                'email': perm['email'],
                                'first_name': perm['first_name'],
                                'last_name': perm['last_name'],
                                'role': perm['role'],
                                'permission_level': perm['permission_level'],
                            }
                        )
                        replaced_count += 1
                    logger.info(f"Replaced with {replaced_count} permissions for document {instance.title}")
                elif permission_action == 'update_level':
                    updated_count = 0
                    for perm in resolved_permissions:
                        existing_perm = existing_permissions.filter(user_id=perm['resolved_user_id']).first()
                        if existing_perm:
                            existing_perm.permission_level = perm['permission_level']
                            existing_perm.save()
                            updated_count += 1
                        else:
                            logger.warning(f"User {perm['resolved_user_id']} not found in existing permissions; skipping update.")
                    logger.info(f"Updated {updated_count} permission levels for document {instance.title}")
        
        return instance


class UserDocumentAccessSerializer(serializers.ModelSerializer):
    document = DocumentSerializer(read_only=True)

    class Meta:
        model = DocumentPermission
        fields = ['document', 'user_id', 'email', 'first_name', 'last_name', 'role', 'permission_level', 'created_at']


class GroupSerializer(serializers.ModelSerializer):
    last_updated_by = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ["id", "name", "description", "tenant", "created_at", "updated_at", "last_updated_by_id", "last_updated_by"]
        read_only_fields = ["id", "tenant", "created_at", "updated_at", "last_updated_by", "last_updated_by_id"]

    def get_last_updated_by(self, obj):
        return get_last_updated_by(self, obj)

    def validate_name(self, value):
        tenant = self.context["request"].user.tenant
        with tenant_context(tenant):
            if self.instance is None and Group.objects.filter(name=value, tenant=tenant).exists():
                raise serializers.ValidationError(f"Group with name '{value}' already exists in this tenant.")
        return value

    def create(self, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            validated_data['last_updated_by_id'] = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for creation")
            raise serializers.ValidationError({"last_updated_by_id": "User ID required for creation."})

        tenant = self.context["request"].user.tenant
        validated_data["tenant"] = tenant
        return super().create(validated_data)


class GroupMembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)
    last_updated_by = serializers.SerializerMethodField()

    class Meta:
        model = GroupMembership
        fields = ["id", "group", "user", "user_email", "group_name", "tenant", "joined_at", "last_updated_by_id", "last_updated_by"]
        read_only_fields = ["id", "tenant", "joined_at", "user_email", "group_name", "last_updated_by", "last_updated_by_id"]

    def get_last_updated_by(self, obj):
        return get_last_updated_by(self, obj)

    def validate(self, data):
        tenant = self.context["request"].user.tenant
        group = data.get("group")
        user = data.get("user")

        with tenant_context(tenant):
            if not Group.objects.filter(id=group.id, tenant=tenant).exists():
                raise serializers.ValidationError({"group": "Group does not belong to this tenant."})
            if not CustomUser.objects.filter(id=user.id, tenant=tenant).exists():
                raise serializers.ValidationError({"user": "User does not belong to this tenant."})
            if GroupMembership.objects.filter(group=group, user=user).exists():
                raise serializers.ValidationError("User is already a member of this group.")
        return data

    def create(self, validated_data):
        user_data = get_user_data_from_jwt(self.context['request'])
        user_id = user_data.get('id')
        if user_id:
            validated_data['last_updated_by_id'] = str(user_id)
        else:
            logger.warning("No user_id found in JWT payload for creation")
            raise serializers.ValidationError({"last_updated_by_id": "User ID required for creation."})

        validated_data["tenant"] = self.context["request"].user.tenant
        return super().create(validated_data)


class UserProfileMinimalSerializer(serializers.ModelSerializer):
    # last_updated_by = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "user",
            "employee_id",
            "access_duration",
            "system_access_rostering",
            "system_access_hr",
            "system_access_recruitment",
            "system_access_training",
            "system_access_finance",
            "system_access_compliance",
            "system_access_co_superadmin",
            "system_access_asset_management",
            # "last_updated_by_id",
            # "last_updated_by",
        ]
        # read_only_fields = ["last_updated_by", "last_updated_by_id"]
# 
    # def get_last_updated_by(self, obj):
    #     return get_last_updated_by(self, obj)




class CustomUserMinimalSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()
    username = serializers.CharField(source='get_username', read_only=True)
    tenant = serializers.CharField(source='tenant.schema_name', read_only=True)
    branch = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "role",
            "job_role",
            "tenant",
            "branch",
            "status",
            "is_locked",
            "has_accepted_terms",
            "profile",
        ]

    def get_profile(self, obj):
        # GlobalUser has no profile → return None
        if not hasattr(obj, 'profile'):
            return None
        if obj.profile:
            return UserProfileMinimalSerializer(obj.profile).data
        return None

    def get_username(self, obj):
        # GlobalUser has no username → fallback to email
        return getattr(obj, 'username', obj.email.split('@')[0])

    def get_branch(self, obj):
        # GlobalUser has no branch
        if not hasattr(obj, 'branch') or not obj.branch:
            return None
        return {"id": obj.branch.id, "name": obj.branch.name}

    def to_representation(self, instance):
        # Handle GlobalUser gracefully
        if not hasattr(instance, 'username'):
            data = {
                "id": instance.id,
                "email": instance.email,
                "username": instance.email.split('@')[0],
                "first_name": instance.first_name or "",
                "last_name": instance.last_name or "",
                "role": getattr(instance, 'role', 'super-admin'),
                "job_role": None,
                "tenant": get_public_schema_name(),
                "branch": None,
                "status": "active",
                "is_locked": False,
                "has_accepted_terms": True,
                "profile": None,
            }
            return data
        return super().to_representation(instance)



class ActivityTypeBreakdownSerializer(serializers.Serializer):
    action = serializers.CharField()
    count = serializers.IntegerField()
    success_count = serializers.IntegerField()
    failure_count = serializers.IntegerField()
    success_rate = serializers.FloatField()

class UserActivityReportSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    role = serializers.CharField()
    activity_count = serializers.IntegerField()
    last_activity = serializers.DateTimeField()

class DailyActivitySerializer(serializers.Serializer):
    date = serializers.DateField()
    count = serializers.IntegerField()
    success_count = serializers.IntegerField()
    failure_count = serializers.IntegerField()

class SystemHealthSerializer(serializers.Serializer):
    timestamp = serializers.DateTimeField()
    system_status = serializers.CharField()
    metrics = serializers.DictField()
    thresholds = serializers.DictField()


class GlobalActivitySerializer(serializers.ModelSerializer):
    affected_tenant_name = serializers.CharField(source='affected_tenant.schema_name', read_only=True)
    performed_by_email = serializers.CharField(source='performed_by.email', read_only=True, allow_null=True)
    global_user_email = serializers.CharField(source='global_user.email', read_only=True, allow_null=True)

    class Meta:
        model = GlobalActivity
        fields = [
            'id', 'global_user', 'global_user_email', 'affected_tenant', 'affected_tenant_name',
            'action', 'performed_by', 'performed_by_email', 'timestamp',
            'details', 'ip_address', 'user_agent', 'success'
        ]
        read_only_fields = ['timestamp']


# New Serializer for Unified Transactions
class TransactionSerializer(serializers.Serializer):
    investor_id = serializers.IntegerField(help_text="User ID of the investor")
    type = serializers.ChoiceField(
        choices=[
            ('deposit', 'Deposit (New Investment)'),
            ('withdrawal', 'Withdrawal'),
            ('roi_payout', 'ROI Payout'),
        ],
        help_text="Type of transaction"
    )
    amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=0)
    # Optional fields
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True, help_text="Optional notes")
    investment_id = serializers.IntegerField(required=False, allow_null=True, help_text="For withdrawals/ROI: Link to existing InvestmentDetail ID")

    def validate_investor_id(self, value):
        try:
            with tenant_context(self.context['request'].user.tenant):
                investor = CustomUser.objects.get(id=value, role='investor')
                if not investor.profile:
                    raise serializers.ValidationError("Investor profile not found.")
                return value
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("Investor not found or not an investor role.")

    def validate(self, data):
        investor_id = data['investor_id']
        txn_type = data['type']
        amount = data['amount']
        investment_id = data.get('investment_id')

        with tenant_context(self.context['request'].user.tenant):
            profile = UserProfile.objects.get(user_id=investor_id)

            if txn_type == 'deposit':
                if amount <= 0:
                    raise serializers.ValidationError({"amount": "Deposit amount must be positive."})
            elif txn_type in ['withdrawal', 'roi_payout']:
                if not investment_id:
                    raise serializers.ValidationError({"investment_id": "Investment ID required for withdrawals/ROI."})
                try:
                    investment = InvestmentDetail.objects.get(id=investment_id, user_profile=profile)
                    available = investment.remaining_balance
                    if amount > available:
                        raise serializers.ValidationError({
                            "amount": f"Amount ({amount}) exceeds available balance ({available})."
                        })
                except InvestmentDetail.DoesNotExist:
                    raise serializers.ValidationError({"investment_id": "Invalid investment ID."})

        return data

    def create(self, validated_data):
        investor_id = validated_data.pop('investor_id')
        txn_type = validated_data.pop('type')
        amount = validated_data.pop('amount')
        notes = validated_data.pop('notes', '')
        investment_id = validated_data.pop('investment_id', None)

        with tenant_context(self.context['request'].user.tenant):
            profile = UserProfile.objects.get(user_id=investor_id)
            user_data = get_user_data_from_jwt(self.context['request'])
            last_updated_by_id = str(user_data['id'])

            if txn_type == 'deposit':
                # Create new InvestmentDetail
                investment = InvestmentDetail.objects.create(
                    user_profile=profile,
                    investment_amount=amount,
                    roi_rate='monthly',  # Default; can be customized
                    last_updated_by_id=last_updated_by_id
                )
                # Log activity
                UserActivity.objects.create(
                    user=profile.user,
                    tenant=profile.user.tenant,
                    action='investment_created',
                    performed_by=self.context['request'].user,
                    details={
                        'amount': str(amount),
                        'investment_id': investment.id,
                        'notes': notes
                    },
                    success=True
                )
                return {
                    'status': 'success',
                    'type': 'deposit',
                    'investment_id': investment.id,
                    'message': f'Deposit of {amount} recorded as new investment.'
                }

            elif txn_type in ['withdrawal', 'roi_payout']:
                # Create WithdrawalDetail
                investment = InvestmentDetail.objects.get(id=investment_id, user_profile=profile)
                withdrawal = WithdrawalDetail.objects.create(
                    investment=investment,
                    user_profile=profile,
                    withdrawal_amount=amount,
                    withdrawal_request_date=timezone.now(),
                    withdrawal_approved=True,  # Auto-approve for simplicity
                    withdrawal_approved_by={
                        'id': last_updated_by_id,
                        'email': user_data['email'],
                        'first_name': user_data['first_name'],
                        'last_name': user_data['last_name'],
                        'role': self.context['request'].user.role
                    },
                    withdrawn_date=timezone.now(),
                    withdrawan=True,
                    last_updated_by_id=last_updated_by_id
                )
                action = 'withdrawal_processed' if txn_type == 'withdrawal' else 'roi_payout_processed'
                # Log activity
                UserActivity.objects.create(
                    user=profile.user,
                    tenant=profile.user.tenant,
                    action=action,
                    performed_by=self.context['request'].user,
                    details={
                        'amount': str(amount),
                        'withdrawal_id': withdrawal.id,
                        'investment_id': investment.id,
                        'type': txn_type,
                        'notes': notes
                    },
                    success=True
                )
                return {
                    'status': 'success',
                    'type': txn_type,
                    'withdrawal_id': withdrawal.id,
                    'message': f'{txn_type.replace("_", " ").title()} of {amount} processed.'
                }

