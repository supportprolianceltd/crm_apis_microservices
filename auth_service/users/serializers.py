from django.db import transaction
from rest_framework import serializers
from .models import CustomUser, UserProfile, ProfessionalQualification, EmploymentDetail, EducationDetail, ReferenceCheck, OtherUserDocuments, PasswordResetToken, ProofOfAddress, InsuranceVerification, DrivingRiskAssessment, LegalWorkEligibility, ClientProfile
from core.models import Module, Domain, Branch
import re
from django.utils import timezone
import logging
from django_tenants.utils import tenant_context
from utils.supabase import upload_file_dynamic
from rest_framework import serializers
from .models import UserSession

logger = logging.getLogger('users')



class ProfessionalQualificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessionalQualification
        fields = ['id', 'name', 'image_file']

    def create(self, validated_data):
        image = validated_data.pop('image_file', None)
        if image:
            url = upload_file_dynamic(image, image.name, content_type=getattr(image, 'content_type', 'application/octet-stream'))
            validated_data['image_file'] = url
        return super().create(validated_data)

    def update(self, instance, validated_data):
        image = validated_data.pop('image_file', None)
        if image:
            url = upload_file_dynamic(image, image.name, content_type=getattr(image, 'content_type', 'application/octet-stream'))
            validated_data['image_file'] = url
        return super().update(instance, validated_data)

class EmploymentDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmploymentDetail
        exclude = ['user_profile']

class EducationDetailSerializer(serializers.ModelSerializer):
    certificate = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = EducationDetail
        fields = '__all__'

    def create(self, validated_data):
        certificate = validated_data.pop('certificate', None)
        if certificate:
            url = upload_file_dynamic(
                certificate,
                certificate.name,
                content_type=getattr(certificate, 'content_type', 'application/octet-stream')
            )
            validated_data['certificate'] = url
        return super().create(validated_data)

    def update(self, instance, validated_data):
        certificate = validated_data.pop('certificate', None)
        if certificate:
            url = upload_file_dynamic(
                certificate,
                certificate.name,
                content_type=getattr(certificate, 'content_type', 'application/octet-stream')
            )
            validated_data['certificate'] = url
        return super().update(instance, validated_data)

class ReferenceCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferenceCheck
        exclude = ['user_profile']

class ProofOfAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProofOfAddress
        exclude = ['user_profile']

    def create(self, validated_data):
        document = validated_data.pop('document', None)
        nin_document = validated_data.pop('nin_document', None)
        if document:
            url = upload_file_dynamic(document, document.name, content_type=getattr(document, 'content_type', 'application/octet-stream'))
            validated_data['document'] = url
        if nin_document:
            url = upload_file_dynamic(nin_document, nin_document.name, content_type=getattr(nin_document, 'content_type', 'application/octet-stream'))
            validated_data['nin_document'] = url
        return super().create(validated_data)

    def update(self, instance, validated_data):
        document = validated_data.pop('document', None)
        nin_document = validated_data.pop('nin_document', None)
        if document:
            url = upload_file_dynamic(document, document.name, content_type=getattr(document, 'content_type', 'application/octet-stream'))
            validated_data['document'] = url
        if nin_document:
            url = upload_file_dynamic(nin_document, nin_document.name, content_type=getattr(nin_document, 'content_type', 'application/octet-stream'))
            validated_data['nin_document'] = url
        return super().update(instance, validated_data)

class InsuranceVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsuranceVerification
        exclude = ['user_profile']

    def create(self, validated_data):
        document = validated_data.pop('document', None)
        if document:
            url = upload_file_dynamic(document, document.name, content_type=getattr(document, 'content_type', 'application/octet-stream'))
            validated_data['document'] = url
        return super().create(validated_data)

    def update(self, instance, validated_data):
        document = validated_data.pop('document', None)
        if document:
            url = upload_file_dynamic(document, document.name, content_type=getattr(document, 'content_type', 'application/octet-stream'))
            validated_data['document'] = url
        return super().update(instance, validated_data)

class DrivingRiskAssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DrivingRiskAssessment
        exclude = ['user_profile']

    def create(self, validated_data):
        supporting_document = validated_data.pop('supporting_document', None)
        if supporting_document:
            url = upload_file_dynamic(supporting_document, supporting_document.name, content_type=getattr(supporting_document, 'content_type', 'application/octet-stream'))
            validated_data['supporting_document'] = url
        return super().create(validated_data)

    def update(self, instance, validated_data):
        supporting_document = validated_data.pop('supporting_document', None)
        if supporting_document:
            url = upload_file_dynamic(supporting_document, supporting_document.name, content_type=getattr(supporting_document, 'content_type', 'application/octet-stream'))
            validated_data['supporting_document'] = url
        return super().update(instance, validated_data)

class LegalWorkEligibilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalWorkEligibility
        exclude = ['user_profile']

    def create(self, validated_data):
        document = validated_data.pop('document', None)
        if document:
            url = upload_file_dynamic(document, document.name, content_type=getattr(document, 'content_type', 'application/octet-stream'))
            validated_data['document'] = url
        return super().create(validated_data)

    def update(self, instance, validated_data):
        document = validated_data.pop('document', None)
        if document:
            url = upload_file_dynamic(document, document.name, content_type=getattr(document, 'content_type', 'application/octet-stream'))
            validated_data['document'] = url
        return super().update(instance, validated_data)

class OtherUserDocumentsSerializer(serializers.ModelSerializer):
    file = serializers.FileField(required=True)
    title = serializers.CharField(required=True)
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = OtherUserDocuments
        fields = ['id', 'title', 'file', 'uploaded_at', 'branch']
        read_only_fields = ['id', 'uploaded_at']

    def validate_file(self, value):
        if not value.name.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg')):
            raise serializers.ValidationError("Only PDF or image files are allowed.")
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("File size cannot exceed 10MB.")
        return value

    def create(self, validated_data):
        file = validated_data.pop('file', None)
        if file:
            url = upload_file_dynamic(file, file.name, content_type=getattr(file, 'content_type', 'application/octet-stream'))
            validated_data['file'] = url
        return super().create(validated_data)

    def update(self, instance, validated_data):
        file = validated_data.pop('file', None)
        if file:
            url = upload_file_dynamic(file, file.name, content_type=getattr(file, 'content_type', 'application/octet-stream'))
            validated_data['file'] = url
        return super().update(instance, validated_data)

class UserProfileSerializer(serializers.ModelSerializer):
    # modules = serializers.SlugRelatedField(
    #     many=True,
    #     required=False,
    #     slug_field='name',
    #     queryset=Module.objects.all()
    # )
    professional_qualifications = ProfessionalQualificationSerializer(many=True, required=False)
    employment_details = EmploymentDetailSerializer(many=True, required=False)
    education_details = EducationDetailSerializer(many=True, required=False)
    reference_checks = ReferenceCheckSerializer(many=True, required=False)
    proof_of_address = ProofOfAddressSerializer(many=True, required=False)
    insurance_verifications = InsuranceVerificationSerializer(many=True, required=False)
    driving_risk_assessments = DrivingRiskAssessmentSerializer(many=True, required=False)
    legal_work_eligibilities = LegalWorkEligibilitySerializer(many=True, required=False)
    other_user_documents = OtherUserDocumentsSerializer(many=True, required=False)
    

    # Explicitly declare image fields for proper URL representation
    profile_image = serializers.ImageField(required=False, allow_null=True)
    drivers_licence_image1 = serializers.ImageField(required=False, allow_null=True)
    drivers_licence_image2 = serializers.ImageField(required=False, allow_null=True)
    Right_to_Work_file = serializers.ImageField(required=False, allow_null=True)
    dbs_certificate = serializers.ImageField(required=False, allow_null=True)
    dbs_update_file = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = UserProfile
        fields = [
            'id', 'user',
            'work_phone', 'personal_phone',
              'gender', 'dob', 'street', 'city', 'state', 'zip_code', 'department',
            'employee_id',  'marital_status',  'profile_image',
            'is_driver', 'type_of_vehicle', 'drivers_licence_image1', 'drivers_licence_image2', 'drivers_licence_country_of_issue',
            'drivers_licence_date_issue', 'drivers_licence_expiry_date', 'drivers_license_insurance_provider',
            'drivers_licence_insurance_expiry_date', 'drivers_licence_issuing_authority', 'drivers_licence_policy_number',
            'assessor_name', 'manual_handling_risk', 'lone_working_risk', 'infection_risk',
            'next_of_kin', 'next_of_kin_address', 'next_of_kin_phone_number', 'next_of_kin_alternate_phone',
            'relationship_to_next_of_kin', 'next_of_kin_email', 'next_of_kin_town', 'next_of_kin_zip_code',
            'Right_to_Work_status', 'Right_to_Work_passport_holder', 'Right_to_Work_document_type', 'Right_to_Work_share_code',
            'Right_to_Work_document_number', 'Right_to_Work_document_expiry_date', 'Right_to_Work_country_of_issue',
            'Right_to_Work_file', 'Right_to_Work_restrictions',
            'dbs_type', 'dbs_certificate', 'dbs_certificate_number', 'dbs_issue_date',
            'dbs_update_file', 'dbs_update_certificate_number', 'dbs_update_issue_date', 'dbs_status_check',
            'bank_name', 'account_number', 'account_name', 'account_type',
            'access_duration', 'system_access_rostering', 'system_access_hr', 'system_access_recruitment',
            'system_access_training', 'system_access_finance', 'system_access_compliance', 'system_access_co_superadmin',
            'system_access_asset_management', 'vehicle_type',
            # Related/reverse fields:
            'professional_qualifications', 'employment_details', 'education_details', 'reference_checks',
            'proof_of_address', 'insurance_verifications', 'driving_risk_assessments', 'legal_work_eligibilities',
            'other_user_documents'
        ]
        read_only_fields = ['id', 'user', 'employee_id']

    def create(self, validated_data):
        image_fields = [
            'profile_image',
            'drivers_licence_image1',
            'drivers_licence_image2',
            'Right_to_Work_file',
            'dbs_certificate',
            'dbs_update_file'
        ]
        # modules = validated_data.pop('modules', [])
        for field in image_fields:
            file = validated_data.pop(field, None)
            if file:
                url = upload_file_dynamic(file, file.name, content_type=getattr(file, 'content_type', 'application/octet-stream'))
                validated_data[field] = url
        profile = super().create(validated_data)
        # if modules:
        #     profile.modules.set(modules)
        return profile

    def update(self, instance, validated_data):
        image_fields = [
            'profile_image',
            'drivers_licence_image1',
            'drivers_licence_image2',
            'Right_to_Work_file',
            'dbs_certificate',
            'dbs_update_file'
        ]
        # modules = validated_data.pop('modules', None)
        for field in image_fields:
            file = validated_data.pop(field, None)
            if file:
                url = upload_file_dynamic(file, file.name, content_type=getattr(file, 'content_type', 'application/octet-stream'))
                validated_data[field] = url
        profile = super().update(instance, validated_data)
        # if modules is not None:
        #     profile.modules.set(modules)
        return profile

class UserCreateSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(required=True)
    #modules = serializers.PrimaryKeyRelatedField(queryset=Module.objects.all(), many=True, required=False)
    documents = OtherUserDocumentsSerializer(many=True, required=False)
    professional_qualifications = ProfessionalQualificationSerializer(many=True, required=False)
    employment_details = EmploymentDetailSerializer(many=True, required=False)
    education_details = EducationDetailSerializer(many=True, required=False)
    reference_checks = ReferenceCheckSerializer(many=True, required=False)
    proof_of_address = ProofOfAddressSerializer(many=True, required=False)
    insurance_verifications = InsuranceVerificationSerializer(many=True, required=False)
    driving_risk_assessments = DrivingRiskAssessmentSerializer(many=True, required=False)
    legal_work_eligibilities = LegalWorkEligibilitySerializer(many=True, required=False)
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    is_superuser = serializers.BooleanField(default=False, required=False)
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'password', 'first_name', 'last_name', 'role', 'job_role',
             'is_superuser', 'last_password_reset','profile','has_accepted_terms',
            'permission_levels', 'documents', 'professional_qualifications',
            'employment_details', 'education_details', 'reference_checks', 'proof_of_address',
            'insurance_verifications', 'driving_risk_assessments', 'legal_work_eligibilities', 'branch'
        ]
        read_only_fields = ['id', 'last_password_reset']
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
        }

    def to_internal_value(self, data):
        mutable_data = data.copy() if hasattr(data, 'copy') else dict(data)
        request = self.context.get('request')

        profile_data = mutable_data.pop('profile', {})
        # Make all profile fields optional: do NOT enforce required fields
        mutable_data['profile'] = profile_data

        for field in ['professional_qualifications', 'employment_details', 'education_details', 'reference_checks',
                     'proof_of_address', 'insurance_verifications', 'driving_risk_assessments', 'legal_work_eligibilities']:
            mutable_data[field] = [dict(item) for item in mutable_data.get(field, [])]

        # modules_data = [data.get(f'modules[{i}]') for i in range(len(data.keys())) if f'modules[{i}]' in data]
        # mutable_data['modules'] = [m for m in modules_data if m]

        return super().to_internal_value(mutable_data)



    def create(self, validated_data):
        if not validated_data.get('username'):
            validated_data['username'] = validated_data['email']
        profile_data = validated_data.pop('profile')

        # Remove all reverse-related fields from profile_data if present
        # modules = profile_data.pop('modules', [])
        professional_qualifications = profile_data.pop('professional_qualifications', [])
        employment_details = profile_data.pop('employment_details', [])
        education_details = profile_data.pop('education_details', [])
        reference_checks = profile_data.pop('reference_checks', [])
        proof_of_address = profile_data.pop('proof_of_address', [])
        insurance_verifications = profile_data.pop('insurance_verifications', [])
        driving_risk_assessments = profile_data.pop('driving_risk_assessments', [])
        legal_work_eligibilities = profile_data.pop('legal_work_eligibilities', [])

        # Remove reverse-related fields from validated_data if present (important!)
        # validated_data.pop('modules', None)
        validated_data.pop('professional_qualifications', None)
        validated_data.pop('employment_details', None)
        validated_data.pop('education_details', None)
        validated_data.pop('reference_checks', None)
        validated_data.pop('proof_of_address', None)
        validated_data.pop('insurance_verifications', None)
        validated_data.pop('driving_risk_assessments', None)
        validated_data.pop('legal_work_eligibilities', None)

        documents = validated_data.pop('documents', [])
        is_superuser = validated_data.pop('is_superuser', False)
        branch = validated_data.pop('branch', None)
        tenant = self.context['request'].user.tenant
        password = validated_data.pop('password')

        with tenant_context(tenant):
            user = CustomUser.objects.create_user(
                **validated_data,
                tenant=tenant,
                branch=branch,
                is_superuser=is_superuser,
                is_staff=is_superuser,
                is_active=validated_data.get('status') == 'active',
                password=password
            )

            profile = UserProfile.objects.create(user=user, **profile_data)
            # profile.modules.set(modules)

            # Now create related objects
            for qual_data in professional_qualifications:
                ProfessionalQualification.objects.create(user_profile=profile, **qual_data)
            for emp_data in employment_details:
                EmploymentDetail.objects.create(user_profile=profile, **emp_data)
            for edu_data in education_details:
                EducationDetail.objects.create(user_profile=profile, **edu_data)
            for ref_data in reference_checks:
                ReferenceCheck.objects.create(user_profile=profile, **ref_data)
            for poa_data in proof_of_address:
                ProofOfAddress.objects.create(user_profile=profile, **poa_data)
            for ins_data in insurance_verifications:
                InsuranceVerification.objects.create(user_profile=profile, **ins_data)
            for dra_data in driving_risk_assessments:
                DrivingRiskAssessment.objects.create(user_profile=profile, **dra_data)
            for lwe_data in legal_work_eligibilities:
                LegalWorkEligibility.objects.create(user_profile=profile, **lwe_data)

            for doc_data in documents:
                OtherUserDocuments.objects.create(
                    user=user,
                    tenant=tenant,
                    title=doc_data['title'],
                    file=doc_data['file'],
                    branch=doc_data.get('branch')
                )

            return user



    def update(self, instance, validated_data):
        with transaction.atomic():
            profile_data = validated_data.pop('profile', None)

            # Pop related fields from both validated_data (root) and profile_data (nested)
            def get_related(field):
                root_val = validated_data.pop(field, None)
                nested_val = profile_data.pop(field, None) if profile_data else None
                return nested_val if nested_val is not None else root_val

            # modules = get_related('modules')
            professional_qualifications = get_related('professional_qualifications')
            employment_details = get_related('employment_details')
            education_details = get_related('education_details')
            reference_checks = get_related('reference_checks')
            proof_of_address = get_related('proof_of_address')
            insurance_verifications = get_related('insurance_verifications')
            driving_risk_assessments = get_related('driving_risk_assessments')
            legal_work_eligibilities = get_related('legal_work_eligibilities')
            documents = validated_data.pop('documents', None)

            # Update user fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            # Update profile if data exists
            profile = getattr(instance, 'profile', None)
            if not profile:
                profile = UserProfile.objects.create(user=instance)

            # Update regular profile fields
            if profile_data:
                # for attr, value in profile_data.items():
                #     setattr(profile, attr, value)
                # profile.save()
                for attr, value in profile_data.items():
                    # Skip reverse/many-related fields
                    if attr not in [
                        'professional_qualifications', 'employment_details', 'education_details',
                        'reference_checks', 'proof_of_address', 'insurance_verifications',
                        'driving_risk_assessments', 'legal_work_eligibilities', 'other_user_documents'
                    ]:
                        setattr(profile, attr, value)
                profile.save()

            # Update many-to-many
            # if modules is not None:
            #     profile.modules.set(modules)

            # Update one-to-many (clear and recreate)
            if professional_qualifications is not None:
                profile.professional_qualifications.all().delete()
                for qual_data in professional_qualifications:
                    qual_data.pop('user_profile', None)  # Remove if present
                    ProfessionalQualification.objects.create(user_profile=profile, **qual_data)

            if employment_details is not None:
                profile.employment_details.all().delete()
                for emp_data in employment_details:
                    emp_data.pop('user_profile', None)  # Remove if present
                    EmploymentDetail.objects.create(user_profile=profile, **emp_data)

            if education_details is not None:
                profile.education_details.all().delete()
                for edu_data in education_details:
                    edu_data.pop('user_profile', None)  # Remove if present
                    EducationDetail.objects.create(user_profile=profile, **edu_data)

            if reference_checks is not None:
                profile.reference_checks.all().delete()
                for ref_data in reference_checks:
                    ref_data.pop('user_profile', None)  # Remove if present
                    ReferenceCheck.objects.create(user_profile=profile, **ref_data)

            if proof_of_address is not None:
                profile.proof_of_address.all().delete()
                for poa_data in proof_of_address:
                    poa_data.pop('user_profile', None)  # Remove if present
                    ProofOfAddress.objects.create(user_profile=profile, **poa_data)

            if insurance_verifications is not None:
                profile.insurance_verifications.all().delete()
                for ins_data in insurance_verifications:
                    ins_data.pop('user_profile', None)  # Remove if present
                    InsuranceVerification.objects.create(user_profile=profile, **ins_data)

            if driving_risk_assessments is not None:
                profile.driving_risk_assessments.all().delete()
                for dra_data in driving_risk_assessments:
                    DrivingRiskAssessment.objects.create(user_profile=profile, **dra_data)

            if legal_work_eligibilities is not None:
                profile.legal_work_eligibilities.all().delete()
                for lwe_data in legal_work_eligibilities:
                    lwe_data.pop('user_profile', None)  # Remove if present
                    LegalWorkEligibility.objects.create(user_profile=profile, **lwe_data)

            # Update user documents
            if documents is not None:
                existing_docs = {doc.id: doc for doc in instance.documents.all()}
                sent_doc_ids = set()
                for doc_data in documents:
                    doc_id = doc_data.get('id')
                    if doc_id:
                        if doc_id in existing_docs:
                            doc = existing_docs[doc_id]
                            for attr, value in doc_data.items():
                                if attr != 'id':
                                    setattr(doc, attr, value)
                            doc.save()
                            sent_doc_ids.add(doc_id)
                        else:
                            raise serializers.ValidationError(f"Invalid UserDocument ID: {doc_id} does not exist.")
                    else:
                        doc_data['user'] = instance
                        doc_data['tenant'] = instance.tenant
                        OtherUserDocuments.objects.create(**doc_data)
                # Optionally delete docs not in sent_doc_ids
                # instance.documents.exclude(id__in=sent_doc_ids).delete()

            return instance

class CustomUserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
   # modules = serializers.SlugRelatedField(many=True, read_only=True, slug_field='name', source='profile.modules')
    tenant = serializers.SlugRelatedField(read_only=True, slug_field='name')
    branch = serializers.SlugRelatedField(read_only=True, slug_field='name', allow_null=True)
    permission_levels = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = CustomUser
        fields = "__all__"
        read_only_fields = ['id', 'is_superuser', 'last_password_reset']

# Other serializers (e.g., AdminUserCreateSerializer, PasswordResetRequestSerializer) remain unchanged unless you specify updates
class AdminUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = CustomUser
        fields = "__all__"
        extra_kwargs = {
            'role': {'required': False, 'default': 'admin'},
            'email': {'required': True},
            'is_superuser': {'default': True},
            'is_staff': {'default': True},
        }

    def validate_email(self, value):
        try:
            domain = value.split('@')[1].lower()
        except IndexError:
            raise serializers.ValidationError("Invalid email format.")
        if not Domain.objects.filter(domain=domain).exists():
            raise serializers.ValidationError(f"No tenant found for domain '{domain}'.")
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError(f"User with email '{value}' already exists.")
        return value

    def create(self, validated_data):
        email = validated_data['email']
        domain = email.split('@')[1].lower()
        domain_obj = Domain.objects.get(domain=domain)
        tenant = domain_obj.tenant
        password = validated_data.pop('password')
        validated_data['is_superuser'] = True
        validated_data['is_staff'] = True
        validated_data['role'] = validated_data.get('role', 'admin')
        validated_data['status'] = validated_data.get('status', 'active')

        from django_tenants.utils import tenant_context
        with tenant_context(tenant):
            user = CustomUser.objects.create_user(
                **validated_data,
                tenant=tenant,
                is_active=True
            )
            user.set_password(password)
            user.save()
            return user

# New serializer for updating user branch
class UserBranchUpdateSerializer(serializers.ModelSerializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = CustomUser
        fields = ['branch']

    def validate_branch(self, value):
        if value is not None:
            tenant = self.context['request'].user.tenant
            with tenant_context(tenant):
                if not Branch.objects.filter(id=value.id, tenant=tenant).exists():
                    raise serializers.ValidationError(f"Branch with ID {value.id} does not belong to tenant {tenant.schema_name}.")
        return value

    def validate(self, data):
        tenant = self.context['request'].user.tenant
        user = self.instance
        if user.tenant != tenant:
            raise serializers.ValidationError("Cannot update branch for a user from a different tenant.")
        return data

    def update(self, instance, validated_data):
        instance.branch = validated_data.get('branch', instance.branch)
        instance.save()
        return instance

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        tenant = self.context['request'].tenant
        with tenant_context(tenant):
            if not CustomUser.objects.filter(email=value, tenant=tenant).exists():
                raise serializers.ValidationError(f"No user found with email '{value}' for this tenant.")
        return value

class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(write_only=True, min_length=8, required=True)

    def validate_token(self, value):
        tenant = self.context['request'].tenant
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
        fields = ['id', 'login_time', 'logout_time', 'duration', 'date', 'ip_address', 'user_agent']




class ClientProfileSerializer(serializers.ModelSerializer):
    preferred_carers = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=CustomUser.objects.filter(role='carer'),
        required=False
    )
    photo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = ClientProfile
        fields = [
            'id', 'user', 'client_id', 'contact_number', 'gender', 'dob', 'nationality',
            'address', 'town', 'zip_code', 'marital_status', 'photo',
            'next_of_kin_name', 'next_of_kin_relationship', 'next_of_kin_address',
            'next_of_kin_phone', 'next_of_kin_email', 'care_plan', 'care_tasks',
            'care_type', 'special_needs', 'preferred_carer_gender', 'language_preference',
            'preferred_care_times', 'frequency_of_care', 'flexibility', 'funding_type',
            'care_package_start_date', 'care_package_review_date', 'preferred_carers',
            'status', 'compliance', 'last_visit'
        ]
        read_only_fields = ['id', 'user', 'client_id']

    def create(self, validated_data):
        photo = validated_data.pop('photo', None)
        preferred_carers = validated_data.pop('preferred_carers', [])
        client_profile = super().create(validated_data)
        if photo:
            from utils.supabase import upload_file_dynamic
            url = upload_file_dynamic(photo, photo.name, content_type=getattr(photo, 'content_type', 'application/octet-stream'))
            client_profile.photo = url
        client_profile.preferred_carers.set(preferred_carers)
        client_profile.save()
        return client_profile

    def update(self, instance, validated_data):
        photo = validated_data.pop('photo', None)
        preferred_carers = validated_data.pop('preferred_carers', None)
        instance = super().update(instance, validated_data)
        if photo:
            from utils.supabase import upload_file_dynamic
            url = upload_file_dynamic(photo, photo.name, content_type=getattr(photo, 'content_type', 'application/octet-stream'))
            instance.photo = url
        if preferred_carers is not None:
            instance.preferred_carers.set(preferred_carers)
        instance.save()
        return instance

class ClientDetailSerializer(serializers.ModelSerializer):
    profile = ClientProfileSerializer()

    class Meta:
        model = CustomUser
        fields = [
            'id', 'email', 'first_name', 'last_name', 'role', 'job_role', 'branch',
            'profile'
        ]
        read_only_fields = ['id', 'role']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.client_profile:
            data['profile'] = ClientProfileSerializer(instance.client_profile).data
        else:
            data['profile'] = None
        return data

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', {})
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
        fields = [
            'id', 'email', 'password', 'first_name', 'last_name', 'role', 'job_role',
            'profile', 'branch'
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'role': {'default': 'client'}
        }

    def create(self, validated_data):
        profile_data = validated_data.pop('profile')
        branch = validated_data.pop('branch', None)
        tenant = self.context['request'].user.tenant
        password = validated_data.pop('password')

        with tenant_context(tenant):
            user = CustomUser.objects.create_user(
                **validated_data,
                tenant=tenant,
                branch=branch,
                is_active=True,
                password=password
            )
            ClientProfile.objects.create(user=user, **profile_data)
            return user


