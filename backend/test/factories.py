import datetime

import factory
from factory import Faker

from court.db.models import PodcastEpisode


class PodcastEpisodeFactory(factory.Factory):
    class Meta:
        model = PodcastEpisode

    guid = factory.Sequence(lambda n: f"episode-guid-{n}")
    title = Faker("sentence", nb_words=5)
    description = Faker("text", max_nb_chars=200)
    pub_date = factory.LazyFunction(lambda: datetime.datetime.now(datetime.UTC))
    duration_seconds = 3600
