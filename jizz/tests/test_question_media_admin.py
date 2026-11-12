from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from jizz.models import Game, Question, Species
from media.models import Media, MediaReview


class QuestionMediaAdminTests(TestCase):
    def test_change_page_links_media_picked_by_number(self):
        sp = Species.objects.create(name='A', name_latin='A a', code='aaa')
        m = [Media.objects.create(species=sp, type='image', url=f'http://x/{i}.jpg', link='', source='test') for i in range(3)]
        admin = User.objects.create_superuser('root', 'r@example.com', 'pw')
        for x in m[1:]:
            MediaReview.objects.create(media=x, review_type='approved', user=admin)
        game = Game.objects.create(media='images')
        q = Question.objects.create(game=game, species=sp, number=1)
        self.client.force_login(admin)
        html = self.client.get(reverse('admin:jizz_question_change', args=[q.pk])).content.decode()
        # number 1 of the two approved media (ordered by id) is the third one
        self.assertIn(reverse('admin:media_media_change', args=[m[2].pk]), html)
