# Standard library
import json
import logging
import mimetypes
import os
import re
import uuid
from datetime import timedelta
from typing import Any, Dict

import jwt
import requests
from core.models import Branch, Domain
from django.conf import settings
from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django_tenants.utils import tenant_context
from drf_spectacular.utils import extend_schema_field
from kafka import KafkaProducer
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from utils.supabase import upload_file_dynamic

from auth_service.utils.jwt_rsa import issue_rsa_jwt

# Local App - Models
from .models import (
    CustomUser,
    EducationDetail,
    EmploymentDetail,
    Group,
    GroupMembership,
    InsuranceVerification,
    LegalWorkEligibility,
    OtherUserDocuments,
    PasswordResetToken,
    ProfessionalQualification,
    ProofOfAddress,
    ReferenceCheck,
    UserActivity,
    UserProfile,
    UserSession,
)

logger = logging.getLogger(__name__)
from rest_framework.exceptions import ValidationError

from .models import Document, DocumentAcknowledgment


def get_tenant_id_from_jwt(request):
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth_header.startswith("Bearer "):
        raise ValidationError("No valid Bearer token provided.")
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("tenant_unique_id")
    except Exception:
        raise ValidationError("Invalid JWT token.")


class ProfessionalQualificationSerializer(serializers.ModelSerializer):
    image_file = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = ProfessionalQualification
        fields = ["id", "name", "image_file"]
        read_only_fields = ["id"]
        extra_kwargs = {
            "name": {"required": True},
            "image_file": {"required": False, "allow_null": True},
        }

    def create(self, validated_data):
        image = validated_data.pop("image_file", None)
        if image:
            logger.info(f"Uploading professional qualification image: {image.name}")
            url = upload_file_dynamic(
                image, image.name, content_type=getattr(image, "content_type", "application/octet-stream")
            )
            validated_data["image_file"] = url
            logger.info(f"Professional qualification image uploaded: {url}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        image = validated_data.pop("image_file", None)
        if image:
            logger.info(f"Updating professional qualification image: {image.name}")
            url = upload_file_dynamic(
                image, image.name, content_type=getattr(image, "content_type", "application/octet-stream")
            )
            validated_data["image_file"] = url
            logger.info(f"Professional qualification image updated: {url}")
        return super().update(instance, validated_data)

    def validate(self, data):
        logger.info(f"Validating ProfessionalQualificationSerializer data: {data}")
        return super().validate(data)


class EmploymentDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmploymentDetail
        exclude = ["user_profile"]
        extra_kwargs = {
            "job_role": {"required": True},
            "hierarchy": {"required": True},
            "department": {"required": True},
            "work_email": {"required": True},
            "employment_type": {"required": True},
            "employment_start_date": {"required": True},
            "salary": {"required": True},
            "working_days": {"required": True},
            "maximum_working_hours": {"required": True},
            "employment_end_date": {"required": False, "allow_null": True},
            "probation_end_date": {"required": False, "allow_null": True},
            "line_manager": {"required": False, "allow_null": True},
            "currency": {"required": False, "allow_null": True},
        }

    def validate(self, data):
        logger.info(f"Validating EmploymentDetailSerializer data: {data}")
        return super().validate(data)


class ReferenceCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferenceCheck
        exclude = ["user_profile"]
        extra_kwargs = {
            "name": {"required": True},
            "phone_number": {"required": True},
            "email": {"required": True},
            "relationship_to_applicant": {"required": True},
        }

    def validate(self, data):
        logger.info(f"Validating ReferenceCheckSerializer data: {data}")
        return super().validate(data)


class EducationDetailSerializer(serializers.ModelSerializer):
    certificate = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = EducationDetail
        exclude = ["user_profile"]
        extra_kwargs = {
            "institution": {"required": True},
            "highest_qualification": {"required": True},
            "course_of_study": {"required": True},
            "start_year": {"required": True, "min_value": 1900, "max_value": 2100},
            "end_year": {"required": True, "min_value": 1900, "max_value": 2100},
            "skills": {"required": True},
            "certificate": {"required": False, "allow_null": True},
            "uploaded_at": {"required": False, "allow_null": True},
        }

    def create(self, validated_data):
        certificate = validated_data.pop("certificate", None)
        if certificate:
            logger.info(f"Uploading education certificate: {certificate.name}")
            url = upload_file_dynamic(
                certificate,
                certificate.name,
                content_type=getattr(certificate, "content_type", "application/octet-stream"),
            )
            validated_data["certificate"] = url
            logger.info(f"Education certificate uploaded: {url}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        certificate = validated_data.pop("certificate", None)
        if certificate:
            logger.info(f"Updating education certificate: {certificate.name}")
            url = upload_file_dynamic(
                certificate,
                certificate.name,
                content_type=getattr(certificate, "content_type", "application/octet-stream"),
            )
            validated_data["certificate"] = url
            logger.info(f"Education certificate updated: {url}")
        return super().update(instance, validated_data)

    def validate(self, data):
        logger.info(f"Validating EducationDetailSerializer data: {data}")
        # Additional validation for start_year <= end_year
        start_year = data.get("start_year")
        end_year = data.get("end_year")
        if start_year and end_year and start_year > end_year:
            raise serializers.ValidationError({"start_year": "Start year cannot be greater than end year."})
        return super().validate(data)


class ProofOfAddressSerializer(serializers.ModelSerializer):
    document = serializers.FileField(required=False, allow_null=True)
    nin_document = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = ProofOfAddress
        exclude = ["user_profile"]
        extra_kwargs = {field: {"required": False, "allow_null": True} for field in ["type", "issue_date", "nin"]}

    def create(self, validated_data):
        document = validated_data.pop("document", None)
        nin_document = validated_data.pop("nin_document", None)
        if document:
            logger.info(f"Uploading proof of address document: {document.name}")
            url = upload_file_dynamic(
                document, document.name, content_type=getattr(document, "content_type", "application/octet-stream")
            )
            validated_data["document"] = url
            logger.info(f"Proof of address document uploaded: {url}")
        if nin_document:
            logger.info(f"Uploading proof of address NIN document: {nin_document.name}")
            url = upload_file_dynamic(
                nin_document,
                nin_document.name,
                content_type=getattr(nin_document, "content_type", "application/octet-stream"),
            )
            validated_data["nin_document"] = url
            logger.info(f"Proof of address NIN document uploaded: {url}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        document = validated_data.pop("document", None)
        nin_document = validated_data.pop("nin_document", None)
        if document:
            logger.info(f"Updating proof of address document: {document.name}")
            url = upload_file_dynamic(
                document, document.name, content_type=getattr(document, "content_type", "application/octet-stream")
            )
            validated_data["document"] = url
            logger.info(f"Proof of address document updated: {url}")
        if nin_document:
            logger.info(f"Updating proof of address NIN document: {nin_document.name}")
            url = upload_file_dynamic(
                nin_document,
                nin_document.name,
                content_type=getattr(nin_document, "content_type", "application/octet-stream"),
            )
            validated_data["nin_document"] = url
            logger.info(f"Proof of address NIN document updated: {url}")
        return super().update(instance, validated_data)


class InsuranceVerificationSerializer(serializers.ModelSerializer):
    document = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = InsuranceVerification
        exclude = ["user_profile"]
        extra_kwargs = {
            field: {"required": False, "allow_null": True}
            for field in ["insurance_type", "provider_name", "coverage_start_date", "coverage_end_date"]
        }

    def create(self, validated_data):
        document = validated_data.pop("document", None)
        if document:
            logger.info(f"Uploading insurance document: {document.name}")
            url = upload_file_dynamic(
                document, document.name, content_type=getattr(document, "content_type", "application/octet-stream")
            )
            validated_data["document"] = url
            logger.info(f"Insurance document uploaded: {url}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        document = validated_data.pop("document", None)
        if document:
            logger.info(f"Updating insurance document: {document.name}")
            url = upload_file_dynamic(
                document, document.name, content_type=getattr(document, "content_type", "application/octet-stream")
            )
            validated_data["document"] = url
            logger.info(f"Insurance document updated: {url}")
        return super().update(instance, validated_data)


class DrivingRiskAssessmentSerializer(serializers.ModelSerializer):
    supporting_document = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = DrivingRiskAssessment
        exclude = ["user_profile"]
        extra_kwargs = {
            field: {"required": False, "allow_null": True}
            for field in ["assessment_date", "fuel_card_usage_compliance", "road_traffic_compliance"]
        }

    def create(self, validated_data):
        supporting_document = validated_data.pop("supporting_document", None)
        if supporting_document:
            logger.info(f"Uploading driving risk assessment document: {supporting_document.name}")
            url = upload_file_dynamic(
                supporting_document,
                supporting_document.name,
                content_type=getattr(supporting_document, "content_type", "application/octet-stream"),
            )
            validated_data["supporting_document"] = url
            logger.info(f"Driving risk assessment document uploaded: {url}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        supporting_document = validated_data.pop("supporting_document", None)
        if supporting_document:
            logger.info(f"Updating driving risk assessment document: {supporting_document.name}")
            url = upload_file_dynamic(
                supporting_document,
                supporting_document.name,
                content_type=getattr(supporting_document, "content_type", "application/octet-stream"),
            )
            validated_data["supporting_document"] = url
            logger.info(f"Driving risk assessment document updated: {url}")
        return super().update(instance, validated_data)


class LegalWorkEligibilitySerializer(serializers.ModelSerializer):
    document = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = LegalWorkEligibility
        exclude = ["user_profile"]
        extra_kwargs = {
            field: {"required": False, "allow_null": True}
            for field in ["evidence_of_right_to_rent", "expiry_date", "phone_number"]
        }

    def create(self, validated_data):
        document = validated_data.pop("document", None)
        if document:
            logger.info(f"Uploading legal work eligibility document: {document.name}")
            url = upload_file_dynamic(
                document, document.name, content_type=getattr(document, "content_type", "application/octet-stream")
            )
            validated_data["document"] = url
            logger.info(f"Legal work eligibility document uploaded: {url}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        document = validated_data.pop("document", None)
        if document:
            logger.info(f"Updating legal work eligibility document: {document.name}")
            url = upload_file_dynamic(
                document, document.name, content_type=getattr(document, "content_type", "application/octet-stream")
            )
            validated_data["document"] = url
            logger.info(f"Legal work eligibility document updated: {url}")
        return super().update(instance, validated_data)


class OtherUserDocumentsSerializer(serializers.ModelSerializer):
    file = serializers.FileField(required=False, allow_null=True)
    title = serializers.CharField(required=False, allow_null=True)
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = OtherUserDocuments
        # fields = ['id', 'title', 'file', 'uploaded_at', 'branch']
        exclude = ["user_profile"]
        read_only_fields = ["id", "uploaded_at"]

    def validate_file(self, value):
        if value and not value.name.lower().endswith((".pdf", ".png", ".jpg", ".jpeg")):
            raise serializers.ValidationError("Only PDF or image files are allowed.")
        if value and value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("File size cannot exceed 10MB.")
        return value

    def create(self, validated_data):
        file = validated_data.pop("file", None)
        if file:
            logger.info(f"Uploading other user document: {file.name}")
            url = upload_file_dynamic(
                file, file.name, content_type=getattr(file, "content_type", "application/octet-stream")
            )
            validated_data["file"] = url
            logger.info(f"Other user document uploaded: {url}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        file = validated_data.pop("file", None)
        if file:
            logger.info(f"Updating other user document: {file.name}")
            url = upload_file_dynamic(
                file, file.name, content_type=getattr(file, "content_type", "application/octet-stream")
            )
            validated_data["file"] = url
            logger.info(f"Other user document updated: {url}")
        return super().update(instance, validated_data)


class UserProfileSerializer(serializers.ModelSerializer):
    professional_qualifications = ProfessionalQualificationSerializer(many=True, required=False, allow_null=True)
    employment_details = EmploymentDetailSerializer(many=True, required=False, allow_null=True)
    education_details = EducationDetailSerializer(many=True, required=False, allow_null=True)
    reference_checks = ReferenceCheckSerializer(many=True, required=False, allow_null=True)
    proof_of_address = ProofOfAddressSerializer(many=True, required=False, allow_null=True)
    insurance_verifications = InsuranceVerificationSerializer(many=True, required=False, allow_null=True)
    driving_risk_assessments = DrivingRiskAssessmentSerializer(many=True, required=False, allow_null=True)
    legal_work_eligibilities = LegalWorkEligibilitySerializer(many=True, required=False, allow_null=True)
    other_user_documents = OtherUserDocumentsSerializer(many=True, required=False, allow_null=True)

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "user",
            "work_phone",
            "personal_phone",
            "gender",
            "dob",
            "street",
            "city",
            "state",
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
            "reference_checks",
            "proof_of_address",
            "insurance_verifications",
            "driving_risk_assessments",
            "legal_work_eligibilities",
            "other_user_documents",
        ]
        read_only_fields = ["id", "user", "employee_id"]
        extra_kwargs = {
            field: {"required": False, "allow_null": True}
            for field in [
                "drivers_licence_date_issue",
                "drivers_licence_expiry_date",
                "drivers_licence_country_of_issue",
                "drivers_license_insurance_provider",
                "drivers_licence_insurance_expiry_date",
                "drivers_licence_issuing_authority",
                "drivers_licence_policy_number",
                "work_phone",
                "personal_phone",
                "gender",
                "dob",
                "street",
                "city",
                "state",
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
                "dbs_certificate_url",
                "dbs_update_file_url",
            ]
        }

    def validate(self, data):
        logger.info(f"Validating UserProfileSerializer data: {data}")
        nested_fields = [
            "professional_qualifications",
            "employment_details",
            "education_details",
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
        return super().validate(data)

    def create(self, validated_data):
        logger.info(f"Creating UserProfile with validated data: {validated_data}")
        nested_fields = [
            ("professional_qualifications", ProfessionalQualificationSerializer, "professional_qualifications"),
            ("employment_details", EmploymentDetailSerializer, "employment_details"),
            ("education_details", EducationDetailSerializer, "education_details"),
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
            ("dbs_certificate", "dbs_certificate_url"),
            ("dbs_update_file", "dbs_update_file_url"),
        ]
        for field, url_field in image_fields:
            file = validated_data.pop(field, None)
            if file and hasattr(file, "name"):
                logger.info(f"Uploading {field}: {file.name}")
                try:
                    url = upload_file_dynamic(
                        file, file.name, content_type=getattr(file, "content_type", "application/octet-stream")
                    )
                    validated_data[url_field] = url
                    logger.info(f"{field} uploaded: {url}")
                except Exception as e:
                    logger.error(f"Failed to upload {field}: {str(e)}")
                    raise serializers.ValidationError(f"Failed to upload {field}: {str(e)}")
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
        logger.info(f"Updating UserProfile instance {instance.id} with validated data: {validated_data}")
        nested_fields = [
            ("professional_qualifications", ProfessionalQualificationSerializer, "professional_qualifications"),
            ("employment_details", EmploymentDetailSerializer, "employment_details"),
            ("education_details", EducationDetailSerializer, "education_details"),
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
            ("dbs_certificate", "dbs_certificate_url"),
            ("dbs_update_file", "dbs_update_file_url"),
        ]
        for field, url_field in image_fields:
            file = validated_data.pop(field, None)
            if file and hasattr(file, "name"):
                logger.info(f"Uploading {field}: {file.name}")
                try:
                    url = upload_file_dynamic(
                        file, file.name, content_type=getattr(file, "content_type", "application/octet-stream")
                    )
                    validated_data[url_field] = url
                    logger.info(f"{field} uploaded: {url}")
                except Exception as e:
                    logger.error(f"Failed to upload {field}: {str(e)}")
                    raise serializers.ValidationError(f"Failed to upload {field}: {str(e)}")
            else:
                logger.info(f"No file provided for {field}, keeping existing {url_field}")
                validated_data[url_field] = getattr(instance, url_field, None)

        updated_instance = super().update(instance, validated_data)

        for field, serializer_class, related_name in nested_fields:
            items = nested_data[field]
            if items is not None:  # Only update if provided
                if items:  # Non-empty array
                    getattr(updated_instance, related_name).all().delete()
                    serializer = serializer_class(data=items, many=True, context=self.context)
                    if serializer.is_valid():
                        try:
                            serializer.save(user_profile=updated_instance)
                            logger.info(f"Updated {len(items)} {field} for profile {updated_instance.id}")
                        except Exception as e:
                            logger.error(f"Failed to save {field} for profile {updated_instance.id}: {str(e)}")
                            logger.error(f"Problematic data: {items}")
                            raise serializers.ValidationError(f"Failed to save {field}: {str(e)}")
                    else:
                        logger.error(f"Validation failed for {field}: {serializer.errors}")
                        raise serializers.ValidationError({field: serializer.errors})
                else:
                    logger.info(f"Empty {field} provided - clearing existing")
                    getattr(updated_instance, related_name).all().delete()
            else:
                logger.info(f"No update for {field} - keeping existing")

        return updated_instance


class UserCreateSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(required=True)
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    is_superuser = serializers.BooleanField(default=False, required=False)
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)

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
            "job_role",
            "is_superuser",
            "last_password_reset",
            "profile",
            "has_accepted_terms",
            "permission_levels",
            "branch",
        ]
        read_only_fields = ["id", "last_password_reset"]
        extra_kwargs = {
            "email": {"required": True},
            "first_name": {"required": True},
            "last_name": {"required": True},
            "username": {"required": False, "allow_null": True},
            "role": {"required": False, "allow_null": True},
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
                "reference_checks",
                "proof_of_address",
                "insurance_verifications",
                "driving_risk_assessments",
                "legal_work_eligibilities",
                "other_user_documents",
            ]

            for field in nested_fields:
                profile_data[field] = []

            for key in data:
                # Handle both prefixed (profile[nested][0][field]) and non-prefixed (nested[0][field]) formats
                if key.startswith("profile[") and key.endswith("]"):
                    # Handle profile-prefixed fields
                    if "][" in key:
                        parts = key.split("[")
                        field_name = parts[1][:-1]  # e.g., professional_qualifications
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

    # def to_internal_value(self, data):
    #     logger.info(f"Raw payload in UserCreateSerializer: {dict(data)}")
    #     mutable_data = {}
    #     profile_data = {}

    #     if hasattr(data, 'getlist'):
    #         # Initialize nested arrays
    #         nested_fields = [
    #             'professional_qualifications',
    #             'employment_details',
    #             'education_details',
    #             'reference_checks',
    #             'proof_of_address',
    #             'insurance_verifications',
    #             'driving_risk_assessments',
    #             'legal_work_eligibilities',
    #             'other_user_documents'
    #         ]

    #         for field in nested_fields:
    #             profile_data[field] = []

    #         for key in data:
    #             if key.startswith('profile[') and key.endswith(']'):
    #                 # Handle nested array fields
    #                 if '][' in key:
    #                     parts = key.split('[')
    #                     field_name = parts[1][:-1]  # e.g., professional_qualifications
    #                     index = int(parts[2][:-1])  # e.g., 0
    #                     sub_field = parts[3][:-1]  # e.g., image_file

    #                     # Ensure the list is long enough
    #                     while len(profile_data.get(field_name, [])) <= index:
    #                         profile_data[field_name].append({})

    #                     # Add value to the appropriate index
    #                     if key in self.context['request'].FILES:
    #                         profile_data[field_name][index][sub_field] = self.context['request'].FILES[key]
    #                     else:
    #                         profile_data[field_name][index][sub_field] = data.get(key)
    #                 else:
    #                     # Handle simple profile fields
    #                     field_name = key[len('profile['):-1]
    #                     if key in self.context['request'].FILES:
    #                         profile_data[field_name] = self.context['request'].FILES[key]
    #                     else:
    #                         profile_data[field_name] = data.get(key)
    #             else:
    #                 mutable_data[key] = data.get(key)
    #     else:
    #         mutable_data = dict(data)
    #         profile_data = mutable_data.get('profile', {})

    #     logger.info(f"Parsed profile data: {profile_data}")
    #     mutable_data['profile'] = profile_data
    #     return super().to_internal_value(mutable_data)

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

            # Create profile using UserProfileSerializer - it will handle nested objects
            profile_serializer = UserProfileSerializer(data=profile_data, context=self.context)
            profile_serializer.is_valid(raise_exception=True)
            profile_serializer.save(user=user)

            return user

    # def update(self, instance, validated_data):
    #     logger.info(f"Updating user {instance.email} with validated data: {validated_data}")
    #     with transaction.atomic():
    #         profile_data = validated_data.pop('profile', {})
    #         for attr, value in validated_data.items():
    #             setattr(instance, attr, value)
    #         instance.save()

    #         profile = getattr(instance, 'profile', None)
    #         if not profile:
    #             profile = UserProfile.objects.create(user=instance)

    #         if profile_data:
    #             logger.info(f"Updating profile for user {instance.email} with data: {profile_data}")
    #             profile_serializer = UserProfileSerializer(profile, data=profile_data, partial=True, context=self.context)
    #             profile_serializer.is_valid(raise_exception=True)
    #             profile_serializer.save()

    #         # Update nested objects (support id-based update for file-only changes)
    #         for model, field, related_name in [
    #             (ProfessionalQualification, 'professional_qualifications', 'professional_qualifications'),
    #             (EducationDetail, 'education_details', 'education_details'),
    #             (ProofOfAddress, 'proof_of_address', 'proof_of_address'),
    #             (EmploymentDetail, 'employment_details', 'employment_details'),
    #             (ReferenceCheck, 'reference_checks', 'reference_checks'),
    #             (InsuranceVerification, 'insurance_verifications', 'insurance_verifications'),
    #             (DrivingRiskAssessment, 'driving_risk_assessments', 'driving_risk_assessments'),
    #             (LegalWorkEligibility, 'legal_work_eligibilities', 'legal_work_eligibilities'),
    #             (OtherUserDocuments, 'other_user_documents', 'other_user_documents'),
    #         ]:
    #             items = profile_data.get(field, None)
    #             if items is not None and len(items) > 0:  # Only process if array is provided and non-empty
    #                 existing_items = {item.id: item for item in getattr(profile, related_name).all()}
    #                 sent_ids = set()
    #                 for item_data in items:
    #                     item_id = item_data.get('id')
    #                     if item_id:
    #                         if item_id in existing_items:
    #                             item = existing_items[item_id]
    #                             for attr, value in item_data.items():
    #                                 if attr != 'id':
    #                                     setattr(item, attr, value)
    #                             item.save()
    #                             sent_ids.add(item_id)
    #                         else:
    #                             logger.warning(f"Invalid {related_name} ID: {item_id} does not exist.")
    #                     else:
    #                         item_data['user_profile'] = profile
    #                         model.objects.create(**item_data)
    #                 # Optional: Delete unsent items
    #                 for item_id in set(existing_items) - sent_ids:
    #                     existing_items[item_id].delete()
    #             else:
    #                 logger.info(f"No update for {field} - skipping (array is empty or not provided)")

    #         return instance

    # def update(self, instance, validated_data):
    #     logger.info(f"Updating user {instance.email} with validated data: {validated_data}")
    #     with transaction.atomic():
    #         profile_data = validated_data.pop('profile', {})
    #         for attr, value in validated_data.items():
    #             setattr(instance, attr, value)
    #         instance.save()

    #         profile = getattr(instance, 'profile', None)
    #         if not profile:
    #             profile = UserProfile.objects.create(user=instance)

    #         if profile_data:
    #             logger.info(f"Updating profile for user {instance.email} with data: {profile_data}")
    #             profile_serializer = UserProfileSerializer(profile, data=profile_data, partial=True, context=self.context)
    #             profile_serializer.is_valid(raise_exception=True)
    #             profile_serializer.save()

    #         return instance

    def update(self, instance, validated_data):
        logger.info(f"Updating user {instance.email} with validated data: {validated_data}")
        with transaction.atomic():
            profile_data = validated_data.pop("profile", {})

            # Update user fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

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

            return instance


class CustomUserListSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    tenant = serializers.SlugRelatedField(read_only=True, slug_field="name")
    branch = serializers.SlugRelatedField(read_only=True, slug_field="name", allow_null=True)
    permission_levels = serializers.ListField(child=serializers.CharField(), required=False)

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
            "profile",
        ]  # Light fields


class CustomUserSerializer(CustomUserListSerializer):
    profile = UserProfileSerializer(read_only=True)
    profile_completion_percentage = serializers.SerializerMethodField()

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

        from django_tenants.utils import tenant_context

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
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        tenant = self.context["request"].tenant
        with tenant_context(tenant):
            if not CustomUser.objects.filter(email=value, tenant=tenant).exists():
                raise serializers.ValidationError(f"No user found with email '{value}' for this tenant.")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(write_only=True, min_length=8, required=True)

    def validate_token(self, value):
        tenant = self.context["request"].tenant
        with tenant_context(tenant):
            try:
                reset_token = PasswordResetToken.objects.get(token=value, tenant=tenant)
                if reset_token.expires_at < timezone.now():
                    raise serializers.ValidationError("This token has expired.")
                if reset_token.used:
                    raise serializers.ValidationError("This token has already been used.")
            except PasswordResetToken.DoesNotExist:
                raise serializers.ValidationError("Invalid token.")
        return value

    def validate_new_password(self, value):
        if not any(c.isupper() for c in value) or not any(c.isdigit() for c in value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter and one number.")
        return value


class UserSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSession
        fields = ["id", "login_time", "logout_time", "duration", "date", "ip_address", "user_agent"]


class ClientProfileSerializer(serializers.ModelSerializer):
    preferred_carers = serializers.PrimaryKeyRelatedField(
        many=True, queryset=CustomUser.objects.filter(role="carer"), required=False
    )
    photo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = ClientProfile
        fields = [
            "id",
            "user",
            "client_id",
            # Personal Information
            "contact_number",
            "gender",
            "dob",
            "nationality",
            "address",
            "town",
            "zip_code",
            "marital_status",
            "photo",
            # Next of Kin
            "next_of_kin_name",
            "next_of_kin_relationship",
            "next_of_kin_address",
            "next_of_kin_phone",
            "next_of_kin_email",
            # Care Requirements
            "care_plan",
            "care_tasks",
            "care_type",
            "special_needs",
            "preferred_carer_gender",
            "language_preference",
            "preferred_care_times",
            "frequency_of_care",
            "flexibility",
            # Administrative & Compliance
            "funding_type",
            "care_package_start_date",
            "care_package_review_date",
            "preferred_carers",
            "status",
            "compliance",
            "last_visit",
            # Company Info
            "company_name",
            "contact_person_name",
            "contact_person_title",
            "contact_person_department",
            "contact_email",
            "contact_phone",
            "company_address",
            # Client Profile Info
            "industry",
            "business_type",
            "client_type",
            # Order and Payment Information
            "order_history",
            "payment_terms",
            "credit_limit",
            "credit_utilization",
            "payment_history",
            # Communication and Feedback
            "communication_preferences",
            "feedback",
            "complaints",
            # Additional Information
            "special_requirements",
            "notes",
        ]

        read_only_fields = ["id", "user", "client_id"]

    def create(self, validated_data):
        photo = validated_data.pop("photo", None)
        preferred_carers = validated_data.pop("preferred_carers", [])
        client_profile = super().create(validated_data)
        if photo:
            from utils.supabase import upload_file_dynamic

            url = upload_file_dynamic(
                photo, photo.name, content_type=getattr(photo, "content_type", "application/octet-stream")
            )
            client_profile.photo = url
        client_profile.preferred_carers.set(preferred_carers)
        client_profile.save()
        return client_profile

    def update(self, instance, validated_data):
        photo = validated_data.pop("photo", None)
        preferred_carers = validated_data.pop("preferred_carers", None)
        instance = super().update(instance, validated_data)
        if photo:
            from utils.supabase import upload_file_dynamic

            url = upload_file_dynamic(
                photo, photo.name, content_type=getattr(photo, "content_type", "application/octet-stream")
            )
            instance.photo = url
        if preferred_carers is not None:
            instance.preferred_carers.set(preferred_carers)
        instance.save()
        return instance


class ClientDetailSerializer(serializers.ModelSerializer):
    profile = ClientProfileSerializer()

    class Meta:
        model = CustomUser
        fields = ["id", "email", "first_name", "last_name", "role", "job_role", "branch", "profile"]
        read_only_fields = ["id", "role"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.client_profile:
            data["profile"] = ClientProfileSerializer(instance.client_profile).data
        else:
            data["profile"] = None
        return data

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", {})
        instance = super().update(instance, validated_data)
        if instance.client_profile:
            profile_serializer = ClientProfileSerializer(instance.client_profile, data=profile_data, partial=True)
            profile_serializer.is_valid(raise_exception=True)
            profile_serializer.save()
        return instance


class ClientCreateSerializer(serializers.ModelSerializer):
    profile = ClientProfileSerializer(required=True)
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = CustomUser
        fields = ["id", "email", "password", "first_name", "last_name", "role", "job_role", "profile", "branch"]
        read_only_fields = ["id"]
        extra_kwargs = {
            "email": {"required": True},
            "first_name": {"required": True},
            "last_name": {"required": True},
            "role": {"default": "client"},
        }

    def create(self, validated_data):
        profile_data = validated_data.pop("profile")
        branch = validated_data.pop("branch", None)
        tenant = self.context["request"].user.tenant
        password = validated_data.pop("password")

        # Ensure JSON fields are dict/list
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
            ClientProfile.objects.create(user=user, **profile_data)
            return user


class DocumentAcknowledgmentSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()  # Display username
    acknowledged_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")

    class Meta:
        model = DocumentAcknowledgment
        fields = ["id", "user", "acknowledged_at"]
        read_only_fields = ["id", "acknowledged_at"]


class DocumentSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.SerializerMethodField()
    updated_by = serializers.SerializerMethodField()
    tenant_domain = serializers.SerializerMethodField()
    file = serializers.FileField(required=False, allow_null=True)  # Add file field for uploads

    class Meta:
        model = Document
        fields = [
            "id",
            "tenant_id",
            "tenant_domain",
            "title",
            "file_url",
            "file_path",
            "file_type",
            "file_size",
            "version",
            "uploaded_by_id",
            "uploaded_by",
            "updated_by_id",
            "updated_by",
            "uploaded_at",
            "updated_at",
            "expiring_date",
            "status",
            "document_number",
            "file",
        ]
        read_only_fields = [
            "id",
            "tenant_id",
            "tenant_domain",
            "uploaded_by_id",
            "updated_by_id",
            "uploaded_at",
            "updated_at",
            "document_number",
            "file_url",
            "file_path",
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
                user_response = requests.get(
                    f"{settings.AUTH_SERVICE_URL}/api/user/users/{obj.uploaded_by_id}/",
                    headers={
                        "Authorization": f'Bearer {self.context["request"].META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'
                    },
                )
                if user_response.status_code == 200:
                    user_data = user_response.json()
                    return {
                        "email": user_data.get("email", ""),
                        "first_name": user_data.get("first_name", ""),
                        "last_name": user_data.get("last_name", ""),
                        "job_role": user_data.get("job_role", ""),
                    }
                logger.error(f"Failed to fetch user {obj.uploaded_by_id} from auth_service")
            except Exception as e:
                logger.error(f"Error fetching uploaded_by {obj.uploaded_by_id}: {str(e)}")
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
                user_response = requests.get(
                    f"{settings.AUTH_SERVICE_URL}/api/user/users/{obj.updated_by_id}/",
                    headers={
                        "Authorization": f'Bearer {self.context["request"].META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'
                    },
                )
                if user_response.status_code == 200:
                    user_data = user_response.json()
                    return {
                        "email": user_data.get("email", ""),
                        "first_name": user_data.get("first_name", ""),
                        "last_name": user_data.get("last_name", ""),
                        "job_role": user_data.get("job_role", ""),
                    }
                logger.error(f"Failed to fetch user {obj.updated_by_id} from auth_service")
            except Exception as e:
                logger.error(f"Error fetching updated_by {obj.updated_by_id}: {str(e)}")
        return None

    @extend_schema_field(str)
    def get_tenant_domain(self, obj):
        try:
            tenant_response = requests.get(
                f"{settings.AUTH_SERVICE_URL}/api/tenant/tenants/{obj.tenant_id}/",
                headers={
                    "Authorization": f'Bearer {self.context["request"].META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'
                },
            )
            if tenant_response.status_code == 200:
                tenant_data = tenant_response.json()
                domains = tenant_data.get("domains", [])
                primary_domain = next((d["domain"] for d in domains if d.get("is_primary")), None)
                return primary_domain
            logger.error(f"Failed to fetch tenant {obj.tenant_id} from auth_service")
        except Exception as e:
            logger.error(f"Error fetching tenant domain for {obj.tenant_id}: {str(e)}")
        return None

    def validate_file(self, value):
        if value:
            if not value.name.lower().endswith((".pdf", ".png", ".jpg", ".jpeg")):
                raise serializers.ValidationError("Only PDF or image files are allowed.")
            if value.size > 10 * 1024 * 1024:  # 10MB limit
                raise serializers.ValidationError("File size cannot exceed 10MB.")
        return value

    def validate(self, data):
        tenant_id = get_tenant_id_from_jwt(self.context["request"])
        data["tenant_id"] = tenant_id  # Inject tenant_id
        if "uploaded_by_id" in data:
            user_response = requests.get(
                f'{settings.AUTH_SERVICE_URL}/api/user/users/{data["uploaded_by_id"]}/',
                headers={"Authorization": self.context["request"].META.get("HTTP_AUTHORIZATION", "")},
            )
            if user_response.status_code != 200:
                raise serializers.ValidationError({"uploaded_by_id": "Invalid user ID."})
            user_data = user_response.json()
            if user_data.get("tenant_id") != tenant_id:
                raise serializers.ValidationError({"uploaded_by_id": "User does not belong to this tenant."})
        if "updated_by_id" in data:
            user_response = requests.get(
                f'{settings.AUTH_SERVICE_URL}/api/user/users/{data["updated_by_id"]}/',
                headers={"Authorization": self.context["request"].META.get("HTTP_AUTHORIZATION", "")},
            )
            if user_response.status_code != 200:
                raise serializers.ValidationError({"updated_by_id": "Invalid user ID."})
            user_data = user_response.json()
            if user_data.get("tenant_id") != tenant_id:
                raise serializers.ValidationError({"updated_by_id": "User does not belong to this tenant."})
        return data

    def create(self, validated_data):
        file = validated_data.pop("file", None)
        tenant_id = get_tenant_id_from_jwt(self.context["request"])
        validated_data["tenant_id"] = str(tenant_id)
        validated_data["uploaded_by_id"] = str(self.context["request"].user.id)
        validated_data["updated_by_id"] = str(self.context["request"].user.id)

        if file:
            logger.info(f"Uploading document file: {file.name}")
            url = upload_file_dynamic(
                file, file.name, content_type=getattr(file, "content_type", "application/octet-stream")
            )
            validated_data["file_url"] = url
            validated_data["file_path"] = url  # Assuming file_path stores the same URL
            validated_data["file_type"] = getattr(file, "content_type", "application/octet-stream")
            validated_data["file_size"] = file.size
            logger.info(f"Document file uploaded: {url}")

        return super().create(validated_data)

    def update(self, instance, validated_data):
        file = validated_data.pop("file", None)
        validated_data["updated_by_id"] = str(self.context["request"].user.id)

        if file:
            logger.info(f"Updating document file: {file.name}")
            url = upload_file_dynamic(
                file, file.name, content_type=getattr(file, "content_type", "application/octet-stream")
            )
            validated_data["file_url"] = url
            validated_data["file_path"] = url  # Assuming file_path stores the same URL
            validated_data["file_type"] = getattr(file, "content_type", "application/octet-stream")
            validated_data["file_size"] = file.size
            logger.info(f"Document file updated: {url}")

        return super().update(instance, validated_data)


class DocumentAcknowledgmentSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = DocumentAcknowledgment
        fields = ["id", "document", "user_id", "user", "acknowledged_at", "tenant_id"]
        read_only_fields = ["id", "user_id", "acknowledged_at", "tenant_id"]

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
    def get_user(self, obj):
        if obj.user_id:
            try:
                user_response = requests.get(
                    f"{settings.AUTH_SERVICE_URL}/api/user/users/{obj.user_id}/",
                    headers={
                        "Authorization": f'Bearer {self.context["request"].META.get("HTTP_AUTHORIZATION", "").split(" ")[1]}'
                    },
                )
                if user_response.status_code == 200:
                    user_data = user_response.json()
                    return {
                        "email": user_data.get("email", ""),
                        "first_name": user_data.get("first_name", ""),
                        "last_name": user_data.get("last_name", ""),
                        "job_role": user_data.get("job_role", ""),
                    }
                logger.error(f"Failed to fetch user {obj.user_id} from auth_service")
            except Exception as e:
                logger.error(f"Error fetching user {obj.user_id}: {str(e)}")
        return None

    def validate(self, data):
        tenant_id = get_tenant_id_from_jwt(self.context["request"])
        data["tenant_id"] = tenant_id
        if "user_id" in data:
            user_response = requests.get(
                f'{settings.AUTH_SERVICE_URL}/api/user/users/{data["user_id"]}/',
                headers={"Authorization": self.context["request"].META.get("HTTP_AUTHORIZATION", "")},
            )
            if user_response.status_code != 200:
                raise serializers.ValidationError({"user_id": "Invalid user ID."})
            user_data = user_response.json()
            if user_data.get("tenant_id") != tenant_id:
                raise serializers.ValidationError({"user_id": "User does not belong to this tenant."})
        return data

    def create(self, validated_data):
        tenant_id = get_tenant_id_from_jwt(self.context["request"])
        validated_data["tenant_id"] = str(tenant_id)
        validated_data["user_id"] = self.context["request"].user.id  # Set from authenticated user
        return super().create(validated_data)


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["id", "name", "description", "tenant", "created_at", "updated_at"]
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]

    def validate_name(self, value):
        tenant = self.context["request"].user.tenant
        with tenant_context(tenant):
            if self.instance is None and Group.objects.filter(name=value, tenant=tenant).exists():
                raise serializers.ValidationError(f"Group with name '{value}' already exists in this tenant.")
        return value

    def create(self, validated_data):
        tenant = self.context["request"].user.tenant
        validated_data["tenant"] = tenant
        return super().create(validated_data)


class GroupMembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = GroupMembership
        fields = ["id", "group", "user", "user_email", "group_name", "tenant", "joined_at"]
        read_only_fields = ["id", "tenant", "joined_at", "user_email", "group_name"]

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
        validated_data["tenant"] = self.context["request"].user.tenant
        return super().create(validated_data)


class UserProfileMinimalSerializer(serializers.ModelSerializer):
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
        ]


class CustomUserMinimalSerializer(serializers.ModelSerializer):
    profile = UserProfileMinimalSerializer(read_only=True)

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


class CustomTokenSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        return super().get_token(user)

    def validate(self, attrs):
        ip_address = self.context["request"].META.get("REMOTE_ADDR")
        user_agent = self.context["request"].META.get("HTTP_USER_AGENT", "")
        tenant = self.context["request"].tenant

        with tenant_context(tenant):
            user = authenticate(email=attrs.get("email"), password=attrs.get("password"))
            if not user:
                UserActivity.objects.create(
                    user=None,
                    tenant=tenant,
                    action="login",
                    performed_by=None,
                    details={"reason": "Invalid credentials"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                raise serializers.ValidationError("Invalid credentials")

            if user.is_locked or not user.is_active:
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action="login",
                    performed_by=None,
                    details={"reason": "Account locked or suspended"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                raise serializers.ValidationError("Account is locked or suspended")

            if BlockedIP.objects.filter(ip_address=ip_address, tenant=tenant, is_active=True).exists():
                UserActivity.objects.create(
                    user=user,
                    tenant=tenant,
                    action="login",
                    performed_by=None,
                    details={"reason": "IP address blocked"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                )
                raise serializers.ValidationError("This IP address is blocked")

            user.reset_login_attempts()
            UserActivity.objects.create(
                user=user,
                tenant=tenant,
                action="login",
                performed_by=None,
                details={},
                ip_address=ip_address,
                user_agent=user_agent,
                success=True,
            )

            access_payload = {
                "jti": str(uuid.uuid4()),
                "sub": user.email,
                "role": user.role,
                "status": user.status,
                "tenant_id": user.tenant.id,
                "tenant_organizational_id": str(tenant.organizational_id),
                "tenant_unique_id": str(tenant.unique_id),
                "tenant_schema": user.tenant.schema_name,
                "has_accepted_terms": user.has_accepted_terms,
                "user": CustomUserMinimalSerializer(user).data,
                "email": user.email,
                "type": "access",
                "exp": (timezone.now() + timedelta(minutes=15)).timestamp(),
            }
            access_token = issue_rsa_jwt(access_payload, user.tenant)

            refresh_jti = str(uuid.uuid4())
            refresh_payload = {
                "jti": refresh_jti,
                "sub": user.email,
                "tenant_id": user.tenant.id,
                "tenant_organizational_id": str(user.tenant.organizational_id),
                "tenant_unique_id": str(user.tenant.unique_id),
                "type": "refresh",
                "exp": (timezone.now() + timedelta(days=7)).timestamp(),
            }
            refresh_token = issue_rsa_jwt(refresh_payload, user.tenant)

            data = {
                "access": access_token,
                "refresh": refresh_token,
                "tenant_id": user.tenant.id,
                "tenant_organizational_id": str(user.tenant.organizational_id),
                "tenant_unique_id": str(user.tenant.unique_id),
                "tenant_schema": user.tenant.schema_name,
                "user": CustomUserMinimalSerializer(user).data,
                "has_accepted_terms": user.has_accepted_terms,
            }
            return data
