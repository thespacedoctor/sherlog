from rest_framework import serializers

from apps.transients.models import Transient


class TransientSerializer(serializers.ModelSerializer):
    """*read/write representation of a transient*

    **Usage:**

    ```python
    serializer = TransientSerializer(data=request.data)
    ```
    """

    # blank=True ON THE MODEL (WHICH THE ADMIN FORM NEEDS) WOULD OTHERWISE MAKE
    # ModelSerializer ACCEPT "" AS WELL AS null, PUTTING BACK THE SECOND EMPTY
    # STATE. THROUGH THE API, "UNCLASSIFIED" IS SPELT null AND ONLY null.
    sherlock_classification = serializers.CharField(
        max_length=10, required=False, allow_null=True, allow_blank=False
    )

    class Meta:
        model = Transient
        fields = [
            "uuid",
            "name",
            "origin",
            "ra",
            "decl",
            "url",
            "sherlock_classification",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["uuid", "created_at", "updated_at"]
        # ModelSerializer DOES NOT GENERATE A UniqueTogetherValidator FOR A
        # UniqueConstraint, ONLY FOR THE LEGACY Meta.unique_together, SO IT IS
        # DECLARED HERE — OTHERWISE A DUPLICATE POST 500s ON THE DB ERROR
        # INSTEAD OF RETURNING 400.
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=Transient.objects.all(),
                fields=["name", "origin"],
            )
        ]
