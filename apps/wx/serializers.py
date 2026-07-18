from rest_framework import serializers
from .models import WxUser, Banner, Announcement, GameCategory, Gift


class WxUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = WxUser
        fields = ['id', 'openid', 'nickname', 'avatar', 'gender', 'phone', 'last_login']


class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = ['id', 'title', 'image', 'link_url']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        image = ret.get('image', '')
        if image and not image.startswith('http'):
            request = self.context.get('request')
            if request:
                ret['image'] = request.build_absolute_uri(image)
        return ret


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ['id', 'title', 'content', 'type', 'created_at']


class GameCategorySerializer(serializers.ModelSerializer):
    icon = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = GameCategory
        fields = ['id', 'name', 'icon', 'sort', 'status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        icon = ret.get('icon', '')
        if icon and not icon.startswith('http'):
            request = self.context.get('request')
            if request:
                ret['icon'] = request.build_absolute_uri(icon)
        return ret


class GiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gift
        fields = ['id', 'name', 'icon', 'price']
