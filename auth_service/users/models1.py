class ProfessionalQualificationSerializer(serializers.ModelSerializer):
    image_file = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = ProfessionalQualification
        fields = ["id", "name", "image_file", "image_file_url"]
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
            validated_data["image_file_url"] = url
            validated_data["image_file"] = None  # Don't save to ImageField
            logger.info(f"Professional qualification image uploaded: {url}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
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
    certificate = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = EducationDetail
        fields = ["id", "institution", "highest_qualification", "course_of_study", "start_year", "end_year", "certificate", "certificate_url", "skills"]
        read_only_fields = ["id"]
        extra_kwargs = {
            "institution": {"required": True},
            "highest_qualification": {"required": True},
            "course_of_study": {"required": True},
            "start_year": {"required": True, "min_value": 1900, "max_value": 2100},
            "end_year": {"required": True, "min_value": 1900, "max_value": 2100},
            "skills": {"required": True},
            "certificate": {"required": False, "allow_null": True},
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
            validated_data["certificate_url"] = url
            validated_data["certificate"] = None  # Don't save to ImageField
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
            validated_data["certificate_url"] = url
            validated_data["certificate"] = None  # Don't save to ImageField
            logger.info(f"Education certificate updated: {url}")
        return super().update(instance, validated_data)

    def validate(self, data):
        logger.info(f"Validating EducationDetailSerializer data: {data}")
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
        fields = ["id", "type", "document", "document_url", "issue_date", "nin", "nin_document", "nin_document_url"]
        read_only_fields = ["id"]
        extra_kwargs = {field: {"required": False, "allow_null": True} for field in ["type", "issue_date", "nin"]}

    def create(self, validated_data):
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
    document = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = InsuranceVerification
        fields = ["id", "insurance_type", "document", "document_url", "provider_name", "coverage_start_date", "expiry_date", "phone_number"]
        read_only_fields = ["id"]
        extra_kwargs = {
            field: {"required": False, "allow_null": True}
            for field in ["insurance_type", "provider_name", "coverage_start_date", "expiry_date", "phone_number"]
        }

    def create(self, validated_data):
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
    supporting_document = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = DrivingRiskAssessment
        fields = ["id", "assessment_date", "fuel_card_usage_compliance", "road_traffic_compliance", "tracker_usage_compliance", "maintenance_schedule_compliance", "additional_notes", "supporting_document", "supporting_document_url"]
        read_only_fields = ["id"]
        extra_kwargs = {
            field: {"required": False, "allow_null": True}
            for field in ["assessment_date", "fuel_card_usage_compliance", "road_traffic_compliance", "tracker_usage_compliance", "maintenance_schedule_compliance", "additional_notes"]
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
            validated_data["supporting_document_url"] = url
            validated_data["supporting_document"] = None  # Don't save to ImageField
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
            validated_data["supporting_document_url"] = url
            validated_data["supporting_document"] = None  # Don't save to ImageField
            logger.info(f"Driving risk assessment document updated: {url}")
        return super().update(instance, validated_data)


class LegalWorkEligibilitySerializer(serializers.ModelSerializer):
    document = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = LegalWorkEligibility
        fields = ["id", "evidence_of_right_to_rent", "document", "document_url", "expiry_date", "phone_number"]
        read_only_fields = ["id"]
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
            validated_data["document_url"] = url
            validated_data["document"] = None  # Don't save to ImageField
            logger.info(f"Legal work eligibility document uploaded: {url}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
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
    file = serializers.FileField(required=False, allow_null=True)
    title = serializers.CharField(required=False, allow_null=True)
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)

    class Meta:
        model = OtherUserDocuments
        fields = ["id", "government_id_type", "title", "document_number", "expiry_date", "file", "file_url", "branch"]
        read_only_fields = ["id"]
        extra_kwargs = {
            "government_id_type": {"required": False},
            "title": {"required": False},
            "document_number": {"required": False},
            "expiry_date": {"required": False},
            "branch": {"required": False},
        }

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
            validated_data["file_url"] = url
            validated_data["file"] = None  # Don't save to ImageField
            logger.info(f"Other user document uploaded: {url}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        file = validated_data.pop("file", None)
        if file:
            logger.info(f"Updating other user document: {file.name}")
            url = upload_file_dynamic(
                file, file.name, content_type=getattr(file, "content_type", "application/octet-stream")
            )
            validated_data["file_url"] = url
            validated_data["file"] = None  # Don't save to ImageField
            logger.info(f"Other user document updated: {url}")
        return super().update(instance, validated_data)

