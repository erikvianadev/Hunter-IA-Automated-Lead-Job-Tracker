from rest_framework import serializers

from .models.models import Job, JobApplication, Lead, Resume, Tag


class ScrapeJobsRequestSerializer(serializers.Serializer):
    query = serializers.CharField(required=False, default="Data Scientist", max_length=255)
    location = serializers.CharField(required=False, default="Remote", max_length=255)


class ResumeUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class ResumeSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Resume
        fields = [
            'id',
            'owner',
            'file',
            'file_url',
            'original_filename',
            'extracted_text',
            'parse_status',
            'content_type',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'owner',
            'original_filename',
            'extracted_text',
            'parse_status',
            'content_type',
            'created_at',
            'updated_at',
        ]

    def get_file_url(self, obj):
        request = self.context.get('request')
        if not obj.file:
            return None
        if request is None:
            return obj.file.url
        return request.build_absolute_uri(obj.file.url)


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class JobSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(),
        source='tags',
        write_only=True,
        required=False,
    )

    class Meta:
        model = Job
        fields = [
            'id',
            'owner',
            'title',
            'company_name',
            'location',
            'description',
            'url',
            'salary',
            'date_posted',
            'tags',
            'tag_ids',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at']


class LeadSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Lead
        fields = [
            'id',
            'owner',
            'name',
            'company',
            'email',
            'linkedin_url',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at']


class JobApplicationSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = JobApplication
        fields = [
            'id',
            'owner',
            'job',
            'status',
            'notes',
            'applied_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at']
