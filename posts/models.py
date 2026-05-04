from django.contrib.auth.models import User
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=80)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        related_name='children',
        on_delete=models.CASCADE,
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['parent', 'name'],
                name='unique_category_name_per_parent',
            ),
        ]
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.path_label

    @property
    def path_names(self):
        names = []
        current = self
        while current:
            names.append(current.name)
            current = current.parent
        return list(reversed(names))

    @property
    def path_label(self):
        return ' > '.join(self.path_names)


class TopicBoard(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=160, unique=True, allow_unicode=True)
    category = models.ForeignKey(
        Category,
        related_name='boards',
        on_delete=models.PROTECT,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['category', 'name'],
                name='unique_board_name_per_category',
            ),
        ]

    def __str__(self):
        return f'{self.category} > {self.name}'

    @property
    def path_label(self):
        return f'{self.category.path_label} > {self.name}'


class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        related_name='profile',
        on_delete=models.CASCADE,
    )
    display_name = models.CharField(max_length=80)
    bio = models.CharField(max_length=160, blank=True)
    photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.display_name


class Subscription(models.Model):
    subscriber = models.ForeignKey(
        User,
        related_name='subscriptions',
        on_delete=models.CASCADE,
    )
    target = models.ForeignKey(
        User,
        related_name='subscribers',
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['subscriber', 'target'],
                name='unique_subscription',
            ),
            models.CheckConstraint(
                condition=~models.Q(subscriber=models.F('target')),
                name='prevent_self_subscription',
            ),
        ]

    def __str__(self):
        return f'{self.subscriber} -> {self.target}'


class Post(models.Model):
    board = models.ForeignKey(
        TopicBoard,
        null=True,
        blank=True,
        related_name='posts',
        on_delete=models.SET_NULL,
    )
    author = models.ForeignKey(
        User,
        null=True,
        blank=True,
        related_name='posts',
        on_delete=models.SET_NULL,
    )
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class PostMedia(models.Model):
    MEDIA_IMAGE = 'image'
    MEDIA_VIDEO = 'video'
    MEDIA_CHOICES = [
        (MEDIA_IMAGE, '사진'),
        (MEDIA_VIDEO, '동영상'),
    ]

    post = models.ForeignKey(
        Post,
        related_name='media',
        on_delete=models.CASCADE,
    )
    file = models.FileField(upload_to='post_media/')
    media_type = models.CharField(max_length=10, choices=MEDIA_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.post.title} {self.media_type}'


class PostLike(models.Model):
    post = models.ForeignKey(
        Post,
        related_name='likes',
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        User,
        related_name='post_likes',
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['post', 'user'],
                name='unique_post_like',
            ),
        ]

    def __str__(self):
        return f'{self.user} likes {self.post}'


class PostComment(models.Model):
    post = models.ForeignKey(
        Post,
        related_name='comments',
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        related_name='post_comments',
        on_delete=models.SET_NULL,
    )
    content = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    @property
    def author_name(self):
        if self.user:
            profile = getattr(self.user, 'profile', None)
            if profile:
                return profile.display_name
            return self.user.username
        return '익명'

    def __str__(self):
        return f'{self.author_name}: {self.content[:30]}'


class ChatMessage(models.Model):
    IDENTITY_ANONYMOUS = 'anonymous'
    IDENTITY_REAL = 'real'
    IDENTITY_CHOICES = [
        (IDENTITY_ANONYMOUS, '익명'),
        (IDENTITY_REAL, '실명'),
    ]

    board = models.ForeignKey(
        TopicBoard,
        null=True,
        blank=True,
        related_name='chat_messages',
        on_delete=models.CASCADE,
    )
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        related_name='chat_messages',
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        related_name='chat_messages',
        on_delete=models.SET_NULL,
    )
    recipient = models.ForeignKey(
        User,
        null=True,
        blank=True,
        related_name='private_chat_messages',
        on_delete=models.CASCADE,
    )
    identity_mode = models.CharField(
        max_length=20,
        choices=IDENTITY_CHOICES,
        default=IDENTITY_ANONYMOUS,
    )
    message = models.CharField(max_length=500)
    image = models.FileField(upload_to='chat_images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    @property
    def sender_name(self):
        if self.identity_mode == self.IDENTITY_REAL and self.user:
            profile = getattr(self.user, 'profile', None)
            if profile:
                return profile.display_name
            return self.user.username
        return '익명'

    def __str__(self):
        return f'{self.sender_name}: {self.message[:30]}'
