from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Category, ChatMessage, Notification, Post, PostLike, Subscription, TopicBoard, UserProfile


class AuthRedirectTests(TestCase):
    def test_landing_page_is_served_at_root(self):
        response = self.client.get(reverse('landing'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'landing.html')
        self.assertContains(response, 'ORBIX')

    def test_feed_home_is_served_at_home_path(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')

    def test_landing_board_input_creates_board_and_enters_it(self):
        response = self.client.post(reverse('landing'), {
            'board_name': 'AI orbit',
        })

        board = TopicBoard.objects.get(name='AI orbit')
        self.assertRedirects(
            response,
            f'/home/?board={board.slug}',
            fetch_redirect_response=False,
        )

    def test_landing_company_board_routes_to_business_analysis(self):
        response = self.client.post(reverse('landing'), {
            'board_name': '삼성물산',
        })

        board = TopicBoard.objects.get(name='삼성물산')
        self.assertEqual(board.category.path_names, ['경제/비즈니스', '투자', '분석'])
        self.assertRedirects(
            response,
            f'/home/?board={board.slug}',
            fetch_redirect_response=False,
        )

    def test_login_redirects_to_home_instead_of_missing_profile_url(self):
        User.objects.create_user(username='orbit', password='password')

        response = self.client.post(reverse('login'), {
            'username': 'orbit',
            'password': 'password',
        })

        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_company_employment_post_routes_to_work_life_context(self):
        user = User.objects.create_user(username='writer', password='password')
        self.client.force_login(user)
        self.client.post(reverse('landing'), {
            'board_name': '삼성물산',
        })
        analysis_board = TopicBoard.objects.get(
            name='삼성물산',
            category__name='분석',
        )

        response = self.client.post(reverse('home'), {
            'title': '삼성물산 채용 연봉 궁금합니다',
            'content': '복지와 면접 분위기가 어떤가요?',
            'board_id': analysis_board.id,
        })

        work_life_board = TopicBoard.objects.get(
            name='삼성물산',
            category__name='직장생활',
        )
        self.assertEqual(work_life_board.category.path_names, ['공부/직업', '커리어', '직장생활'])
        self.assertEqual(Post.objects.get(title='삼성물산 채용 연봉 궁금합니다').board, work_life_board)
        self.assertEqual(TopicBoard.objects.filter(name='삼성물산').count(), 2)
        self.assertRedirects(
            response,
            f'/home/?board={work_life_board.slug}',
            fetch_redirect_response=False,
        )

    def test_header_search_filters_posts_and_exposes_shortcuts(self):
        user = User.objects.create_user(username='samsung_writer', password='password')
        self.client.post(reverse('landing'), {
            'board_name': '삼성물산',
        })
        board = TopicBoard.objects.get(name='삼성물산')
        matching_post = Post.objects.create(
            author=user,
            board=board,
            title='삼성물산 실적 분석',
            content='기업분석 내용입니다.',
        )
        Post.objects.create(title='다른 이야기', content='검색에서 제외됩니다.')

        response = self.client.get(reverse('home'), {'q': '삼성물산'})

        self.assertContains(response, '삼성물산')
        self.assertEqual(response.context['search_query'], '삼성물산')
        self.assertEqual([post.id for post in response.context['posts']], [matching_post.id])
        self.assertEqual(response.context['search_boards'][0], board)
        self.assertNotContains(response, '새 게시글')

    def test_empty_category_shows_clickable_new_orbit_button(self):
        category = Category.objects.create(name='빈 소분류')

        response = self.client.get(reverse('home'), {'category': category.id})

        self.assertEqual(response.context['board_search_category'], category)
        self.assertContains(response, 'data-focus-board-search')
        self.assertContains(response, '새 궤도 생성')

    def test_home_exposes_featured_real_time_orbits(self):
        response = self.client.get(reverse('home'))

        names = [item['name'] for item in response.context['featured_orbits']]
        self.assertIn('주식', names)
        self.assertIn('기업분석', names)
        self.assertIn('패션', names)
        self.assertContains(response, '오늘 뜨는 궤도')

    def test_fashion_style_board_routes_to_fashion_category(self):
        response = self.client.post(reverse('landing'), {
            'board_name': '아메카지',
        })

        board = TopicBoard.objects.get(name='아메카지')
        self.assertEqual(board.category.path_names, ['생활/취미', '패션/뷰티', '패션'])
        self.assertRedirects(
            response,
            f'/home/?board={board.slug}',
            fetch_redirect_response=False,
        )

    def test_known_board_route_sync_moves_legacy_fashion_board(self):
        legacy_category = Category.objects.create(name='기타')
        legacy_board = TopicBoard.objects.create(
            name='아메카지',
            slug='legacy-american-casual',
            category=legacy_category,
        )

        self.client.get(reverse('home'))
        legacy_board.refresh_from_db()

        self.assertEqual(legacy_board.category.path_names, ['생활/취미', '패션/뷰티', '패션'])

    def test_popular_boards_ignore_legacy_taxonomy_branches(self):
        legacy_category = Category.objects.create(name='취미')
        legacy_board = TopicBoard.objects.create(name='옛 게시판', slug='legacy-board', category=legacy_category)
        self.client.post(reverse('landing'), {
            'board_name': '아메카지',
        })
        current_board = TopicBoard.objects.get(name='아메카지')
        Post.objects.create(board=legacy_board, title='legacy', content='legacy')
        Post.objects.create(board=current_board, title='current', content='current')

        response = self.client.get(reverse('home'))

        popular_names = [board.name for board in response.context['popular_boards']]
        self.assertIn(current_board.name, popular_names)
        self.assertNotIn(legacy_board.name, popular_names)


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

    def test_home_exposes_recent_chat_links_for_joined_rooms(self):
        category = Category.objects.create(name='Tech')
        board = TopicBoard.objects.create(name='Django', slug='django', category=category)
        outsider = User.objects.create_user(username='outsider', password='password')
        ChatMessage.objects.create(
            user=self.viewer,
            board=board,
            message='board hello',
        )
        ChatMessage.objects.create(
            user=self.followed,
            recipient=self.viewer,
            message='private hello',
        )
        ChatMessage.objects.create(
            user=outsider,
            board=board,
            message='not mine',
        )

        response = self.client.get(reverse('home'))
        links = response.context['recent_chat_links']

        self.assertEqual(links[0]['label'], self.followed.username)
        self.assertEqual(links[0]['href'], f'/home/?chat=private&private_user={self.followed.id}')
        self.assertTrue(any(link['label'] == board.name and link['href'] == f'/home/?board={board.slug}' for link in links))


class RedesignedBackendCompatibilityTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(username='viewer', password='password12345')
        self.target = User.objects.create_user(username='target', password='password12345')
        self.post = Post.objects.create(
            author=self.target,
            title='compatible post',
            content='new frontend can open this post',
        )

    def test_user_profile_is_created_by_signal(self):
        user = User.objects.create_user(username='fresh_user', password='password12345')

        self.assertTrue(UserProfile.objects.filter(user=user, display_name='fresh_user').exists())

    def test_named_routes_for_redesigned_frontend_are_routable(self):
        routes = [
            reverse('feed'),
            reverse('profile', args=[self.target.username]),
            reverse('profile_edit'),
            reverse('orbit_toggle', args=[self.target.username]),
            reverse('notifications'),
            reverse('explore'),
            reverse('post_detail_singular', args=[self.post.id]),
            reverse('post_like', args=[self.post.id]),
            reverse('post_comment', args=[self.post.id]),
        ]

        self.assertTrue(all(routes))

    def test_auth_templates_use_django_form_field_names(self):
        signup = self.client.get(reverse('signup'))
        login = self.client.get(reverse('login'))

        self.assertContains(signup, 'name="username"')
        self.assertContains(signup, 'name="password1"')
        self.assertContains(signup, 'name="password2"')
        self.assertContains(login, 'name="username"')
        self.assertContains(login, 'name="password"')

    def test_signup_accepts_legacy_single_password_field(self):
        response = self.client.post(reverse('signup'), {
            'username': 'legacy_signup',
            'password': 'legacy-pass-12345',
        })

        self.assertRedirects(response, reverse('home'))
        self.assertTrue(User.objects.filter(username='legacy_signup').exists())

    def test_profile_view_exposes_orbit_context_names(self):
        Subscription.objects.create(subscriber=self.viewer, target=self.target)
        self.client.force_login(self.viewer)

        response = self.client.get(reverse('profile', args=[self.target.username]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['profile_user'], self.target)
        self.assertTrue(response.context['is_orbiting'])
        self.assertEqual(response.context['orbiters_count'], 1)
        self.assertEqual(response.context['orbiting_count'], 0)
        self.assertEqual(list(response.context['posts']), [self.post])

    def test_orbit_toggle_returns_ajax_payload_and_counts(self):
        self.client.force_login(self.viewer)

        follow = self.client.post(reverse('orbit_toggle', args=[self.target.username]))
        unfollow = self.client.post(reverse('orbit_toggle', args=[self.target.username]))

        self.assertTrue(follow.json()['orbiting'])
        self.assertEqual(follow.json()['orbiters_count'], 1)
        self.assertFalse(unfollow.json()['orbiting'])
        self.assertEqual(unfollow.json()['orbiters_count'], 0)

    def test_post_like_returns_ajax_payload_and_counts(self):
        self.client.force_login(self.viewer)

        liked = self.client.post(reverse('post_like', args=[self.post.id]))
        unliked = self.client.post(reverse('post_like', args=[self.post.id]))

        self.assertTrue(liked.json()['liked'])
        self.assertEqual(liked.json()['count'], 1)
        self.assertFalse(unliked.json()['liked'])
        self.assertEqual(unliked.json()['count'], 0)
        self.assertFalse(PostLike.objects.filter(post=self.post, user=self.viewer).exists())
