from rest_framework import serializers
from .models import WxUser, Banner, Announcement, GameCategory, Gift, GameBanner


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
    banner = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = GameCategory
        fields = ['id', 'name', 'icon', 'banner', 'description', 'sort', 'status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        request = self.context.get('request')
        for field in ('icon', 'banner'):
            image_url = ret.get(field, '')
            if image_url and not image_url.startswith('http') and request:
                ret[field] = request.build_absolute_uri(image_url)
        return ret


class GiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gift
        fields = ['id', 'name', 'icon', 'price']


class GameBannerSerializer(serializers.ModelSerializer):
    """小程序端游戏轮播图序列化"""
    class Meta:
        model = GameBanner
        fields = ['id', 'game', 'title', 'image', 'link_url']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        image = ret.get('image', '')
        if image and not image.startswith('http'):
            request = self.context.get('request')
            if request:
                ret['image'] = request.build_absolute_uri(image)
        return ret


class GameBannerManageSerializer(serializers.ModelSerializer):
    """管理后台游戏轮播图序列化"""
    game_name = serializers.CharField(source='game.name', read_only=True)

    class Meta:
        model = GameBanner
        fields = ['id', 'game', 'game_name', 'title', 'image', 'link_url', 'sort', 'status', 'created_at']
        read_only_fields = ['id', 'created_at']
