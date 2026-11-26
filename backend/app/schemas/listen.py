import uuid
from typing import Annotated

from pydantic import BaseModel, Field

from app.services.task_status import TaskStatus

# Question and option numbers count from 1; every Listen Dialogue has three of each.
QuestionNumber = Annotated[int, Field(ge=1, le=3)]
OptionNumber = Annotated[int, Field(ge=1, le=3)]


class ListenLine(BaseModel):
    """One line of the Listen Dialogue: who says it, and what they say."""

    speaker: str
    text: str


class GivenAnswer(BaseModel):
    """The User's answer to a Comprehension Question, now that it's final."""

    choice: OptionNumber
    correct: bool
    correct_option: OptionNumber


class ListenQuestion(BaseModel):
    """A Comprehension Question with its three options. `answer` is null until the User
    answers it, so the correct option is never sent before then."""

    number: QuestionNumber
    prompt: str
    options: list[str]
    answer: GivenAnswer | None


class ListenTask(BaseModel):
    """A Listen Task's Listen Dialogue and its three Comprehension Questions.

    The dialogue is fixed the first time the Task is opened or answered, so it's the
    same every time. `answerable` is true only while the questions can still be
    answered: on the Task's own Plan Day, while the Event is Active and the Task isn't
    complete. A Missed Task, a later Plan Day's, or a Past Event's is read-only.
    """

    task_id: uuid.UUID
    status: TaskStatus
    answerable: bool
    speakers: list[str]
    lines: list[ListenLine]
    questions: list[ListenQuestion]


class ListenAnswerCreate(BaseModel):
    """An answer to one Comprehension Question: its number and the chosen option's."""

    question: QuestionNumber
    choice: OptionNumber


class ListenAnswerResult(BaseModel):
    """Whether the answer was right, the correct option, and the Task's status: the
    third answer completes it."""

    task_id: uuid.UUID
    question: QuestionNumber
    choice: OptionNumber
    correct: bool
    correct_option: OptionNumber
    status: TaskStatus
