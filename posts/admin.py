from django.contrib import admin
from .models import Category, ChatMessage, Post, PostComment, PostLike, PostMedia, Subscription, TopicBoard, UserProfile


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'order')
    list_filter = ('parent',)
    search_fields = ('name',)
    actions = None

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TopicBoard)
class TopicBoardAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'post_count', 'chat_count', 'created_at')
    list_filter = ('category',)
    search_fields = ('name', 'category__name')
    prepopulated_fields = {'slug': ('name',)}

    @admin.display(description='posts')
    def post_count(self, obj):
        return obj.posts.count()

    @admin.display(description='chats')
    def chat_count(self, obj):
        return obj.chat_messages.count()


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'board', 'created_at')
    list_filter = ('board',)
    search_fields = ('title', 'content')


@admin.register(PostMedia)
class PostMediaAdmin(admin.ModelAdmin):
    list_display = ('post', 'media_type', 'created_at')
    list_filter = ('media_type',)


@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    list_display = ('post', 'user', 'created_at')
    search_fields = ('post__title', 'user__username')


@admin.register(PostComment)
class PostCommentAdmin(admin.ModelAdmin):
    list_display = ('post', 'author_name', 'created_at')
    search_fields = ('post__title', 'content', 'user__username')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'user', 'created_at')
    search_fields = ('display_name', 'user__username')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('subscriber', 'target', 'created_at')
    search_fields = ('subscriber__username', 'target__username')
    list_filter = ('created_at',)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('sender_name', 'identity_mode', 'board', 'category', 'recipient', 'created_at')
    list_filter = ('identity_mode', 'board', 'category')
    search_fields = ('message', 'user__username', 'user__profile__display_name', 'recipient__username')
