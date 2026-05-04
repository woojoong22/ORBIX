from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Notification, Post, Subscription


class FollowEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='orbit', password='password')
        self.target = User.objects.create_user(username='target', password='password')
        self.other = User.objects.create_user(username='other', password='password')
        self.client.force_login(self.user)

    def test_follow_creates_subscription_and_returns_counts(self):
        response = self.client.post(reverse('follow_account', args=[self.target.username]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Subscription.objects.filter(subscriber=self.user, target=self.target).exists())
        self.assertTrue(Notification.objects.filter(
            actor=self.user,
            recipient=self.target,
            verb=Notification.VERB_FOLLOW,
        ).exists())
        self.assertEqual(response.json()['status'], 'followed')
        self.assertTrue(response.json()['changed'])
        self.assertEqual(response.json()['follower_count'], 1)
        self.assertEqual(response.json()['following_count'], 0)

    def test_duplicate_follow_is_idempotent(self):
        Subscription.objects.create(subscriber=self.user, target=self.target)
        Notification.objects.create(
            actor=self.user,
            recipient=self.target,
            verb=Notification.VERB_FOLLOW,
        )

        response = self.client.post(reverse('follow_account', args=[self.target.username]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'already_following')
        self.assertFalse(response.json()['changed'])
        self.assertEqual(Subscription.objects.filter(subscriber=self.user, target=self.target).count(), 1)
        self.assertEqual(Notification.objects.filter(
            actor=self.user,
            recipient=self.target,
            verb=Notification.VERB_FOLLOW,
        ).count(), 1)

    def test_unfollow_removes_subscription_and_returns_counts(self):
        Subscription.objects.create(subscriber=self.user, target=self.target)
        Subscription.objects.create(subscriber=self.other, target=self.target)

        response = self.client.post(reverse('unfollow_account', args=[self.target.username]))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Subscription.objects.filter(subscriber=self.user, target=self.target).exists())
        self.assertEqual(response.json()['status'], 'unfollowed')
        self.assertTrue(response.json()['changed'])
        self.assertEqual(response.json()['follower_count'], 1)

    def test_unfollow_without_existing_subscription_is_idempotent(self):
        response = self.client.post(reverse('unfollow_account', args=[self.target.username]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'not_following')
        self.assertFalse(response.json()['changed'])
        self.assertEqual(response.json()['follower_count'], 0)

    def test_self_follow_is_blocked(self):
        response = self.client.post(reverse('follow_account', args=[self.user.username]))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'self_follow_blocked')
        self.assertFalse(Subscription.objects.filter(subscriber=self.user, target=self.user).exists())

    def test_follow_state_exposes_counts(self):
        Subscription.objects.create(subscriber=self.user, target=self.target)
        Subscription.objects.create(subscriber=self.target, target=self.other)

        response = self.client.get(reverse('follow_state', args=[self.target.username]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['is_following'])
        self.assertEqual(response.json()['follower_count'], 1)
        self.assertEqual(response.json()['following_count'], 1)


class FollowingFeedTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(username='viewer', password='password')
        self.followed = User.objects.create_user(username='followed', password='password')
        self.unfollowed = User.objects.create_user(username='unfollowed', password='password')
        self.followed_post = Post.objects.create(
            author=self.followed,
            title='followed post',
            content='visible in following feed',
        )
        self.unfollowed_post = Post.objects.create(
            author=self.unfollowed,
            title='unfollowed post',
            content='hidden from following feed',
        )
        self.client.force_login(self.viewer)

    def assertFeedTitles(self, response, expected_titles):
        self.assertEqual(
            [post.title for post in response.context['posts']],
            expected_titles,
        )

    def test_default_feed_keeps_all_posts(self):
        response = self.client.get(reverse('home'))

        self.assertFeedTitles(response, [self.unfollowed_post.title, self.followed_post.title])

    def test_following_feed_only_returns_followed_author_posts(self):
        Subscription.objects.create(subscriber=self.viewer, target=self.followed)

        response = self.client.get(reverse('home'), {'feed': 'following'})

        self.assertFeedTitles(response, [self.followed_post.title])

    def test_no_following_feed_returns_no_user_posts(self):
        response = self.client.get(reverse('home'), {'feed': 'following'})

        self.assertFeedTitles(response, [])

    def test_unfollow_removes_author_from_following_feed_immediately(self):
        Subscription.objects.create(subscriber=self.viewer, target=self.followed)
        self.client.post(reverse('unfollow_account', args=[self.followed.username]))

        response = self.client.get(reverse('home'), {'feed': 'following'})

        self.assertFeedTitles(response, [])

    def test_following_feed_tolerates_page_parameter(self):
        Subscription.objects.create(subscriber=self.viewer, target=self.followed)

        response = self.client.get(reverse('home'), {'feed': 'following', 'page': '1'})

        self.assertEqual(response.status_code, 200)
        self.assertFeedTitles(response, [self.followed_post.title])

    def test_home_post_card_follow_button_toggles_subscription(self):
        response = self.client.post(reverse('home'), {
            'action': 'toggle_subscription',
            'username': self.followed.username,
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Subscription.objects.filter(
            subscriber=self.viewer,
            target=self.followed,
        ).exists())
        self.assertTrue(Notification.objects.filter(
            actor=self.viewer,
            recipient=self.followed,
            verb=Notification.VERB_FOLLOW,
        ).exists())

    def test_like_and_comment_create_notifications(self):
        self.client.post(reverse('post_detail', args=[self.followed_post.id]), {
            'action': 'toggle_like',
        })
        self.client.post(reverse('post_detail', args=[self.followed_post.id]), {
            'action': 'add_comment',
            'content': 'nice orbit',
        })

        self.assertTrue(Notification.objects.filter(
            actor=self.viewer,
            recipient=self.followed,
            post=self.followed_post,
            verb=Notification.VERB_LIKE,
        ).exists())
        self.assertTrue(Notification.objects.filter(
            actor=self.viewer,
            recipient=self.followed,
            post=self.followed_post,
            verb=Notification.VERB_COMMENT,
        ).exists())
