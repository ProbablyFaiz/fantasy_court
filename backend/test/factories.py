import factory
from factory import Faker

from blank.db.models import Task, TaskPriority


class TaskFactory(factory.Factory):
    class Meta:
        model = Task

    title = Faker("sentence", nb_words=4)
    description = Faker("text", max_nb_chars=200)
    completed = False
    priority = TaskPriority.MEDIUM
