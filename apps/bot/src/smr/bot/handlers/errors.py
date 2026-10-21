"""What people see when something goes wrong; nothing personal reaches the logs."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import ExceptionTypeFilter
from aiogram.types import ErrorEvent
from aiogram_dialog import DialogManager
from aiogram_dialog.api.exceptions import UnknownIntent, UnknownState

from smr.bdz.domain import BdzError
from smr.core.access import NotAdminError
from smr.core.files import (
    FileTooLargeError,
    PdfBrokenError,
    PdfLockedError,
    UnsupportedFileError,
)
from smr.gradebook.domain import GradebookError
from smr.homework.domain import HomeworkError
from smr.materials.domain import MaterialsError
from smr.review.domain import AppealNotAllowedError, ReviewError
from smr.roster.domain import GroupArchivedError, RosterError
from smr.sessions.domain import SessionsError

logger = logging.getLogger(__name__)
router = Router(name="errors")

_KNOWN: tuple[type[Exception], ...] = (
    RosterError,
    GradebookError,
    SessionsError,
    HomeworkError,
    MaterialsError,
    BdzError,
    ReviewError,
    PdfBrokenError,
    PdfLockedError,
    ValueError,
)


async def _tell(event: ErrorEvent, text: str) -> None:
    update = event.update
    if update.callback_query is not None:
        _ = await update.callback_query.answer(text, show_alert=True)
    elif update.message is not None:
        _ = await update.message.answer(text)


@router.error(ExceptionTypeFilter(UnknownIntent, UnknownState))
async def restart(event: ErrorEvent, dialog_manager: DialogManager) -> None:
    """Old buttons after a restart: the dialog is gone, so start over."""
    await _tell(event, "Бот обновился. Нажмите /start.")
    await dialog_manager.reset_stack()


@router.error(ExceptionTypeFilter(NotAdminError))
async def not_admin(event: ErrorEvent) -> None:
    """A student reached a teacher's action."""
    await _tell(event, "Это действие только для преподавателя.")


@router.error(ExceptionTypeFilter(GroupArchivedError))
async def archived(event: ErrorEvent) -> None:
    """The group is read-only."""
    await _tell(event, "Группа в архиве: изменения невозможны.")


@router.error(ExceptionTypeFilter(FileTooLargeError, UnsupportedFileError))
async def bad_file(event: ErrorEvent) -> None:
    """A file the store refused."""
    await _tell(event, "Файл не подходит: нужен PDF, DOCX или фото не больше 20 МБ.")


@router.error(ExceptionTypeFilter(*_KNOWN))
async def known(event: ErrorEvent) -> None:
    """A rule of the domain said no."""
    logger.info("refused: %s", type(event.exception).__name__)
    await _tell(event, f"Не получилось: {_reason(event.exception)}")


@router.error()
async def unexpected(event: ErrorEvent) -> None:
    """Anything else: log the type and the update id, never the content."""
    logger.error(
        "unexpected %s in update %s",
        type(event.exception).__name__,
        event.update.update_id,
        exc_info=event.exception,
    )
    await _tell(event, "Что-то пошло не так. Попробуйте ещё раз или нажмите /start.")


_REASONS: dict[str, str] = {
    "GroupNotFoundError": "группа не найдена",
    "InviteNotFoundError": "ссылка устарела",
    "StudentNotFoundError": "студент не найден",
    "NameTakenError": "фамилию уже выбрали",
    "AlreadyBoundError": "вы уже в этой группе",
    "DuplicateNameError": "такое ФИО уже есть в группе",
    "JournalNumberTakenError": "этот номер в журнале уже у другого студента",
    "NotPendingError": "заявка уже обработана",
    "WorkTypeNotFoundError": "в группе нет такого вида работы — примените схему баллов",
    "WorkTypeInUseError": "по этому виду работы уже есть баллы",
    "WorkTypeKindTakenError": "такой вид работы в группе уже есть",
    "ItemNotFoundError": "позиция не найдена",
    "EntryNotFoundError": "запись не найдена",
    "PointsOutOfRangeError": "баллы вне допустимого диапазона",
    "SessionNotFoundError": "занятие не найдено",
    "BoardCallNotFoundError": "вызов не найден",
    "StudentNotInGroupError": "студента нет в группе",
    "NoCandidatesError": "все присутствующие уже выходили",
    "AssignmentNotFoundError": "задание не найдено",
    "NotYourAssignmentError": "это задание не вашей группы",
    "SubmissionNotFoundError": "работа не найдена",
    "SubmissionClosedError": "работа уже проверена",
    "DraftEmptyError": "черновик пуст",
    "TooManyFilesError": "слишком много файлов",
    "MaterialNotFoundError": "материал не найден",
    "EmptyMaterialError": "в карточке нет файлов",
    "WorkTypeNotProportionalError": (
        "БДЗ ставится на вид работы с долей баллов, не на накопительный"
    ),
    "NotAPdfError": "нужен один PDF-файл",
    "PdfLockedError": "PDF защищён паролем — снимите пароль и пришлите снова",
    "PdfBrokenError": "не получается открыть PDF — пересоберите файл",
    "TooManyPagesError": "слишком много страниц (больше 60)",
    "ConsentRequiredError": "сначала примите обновлённое согласие: /start",
    "AppealOpenError": "пока идёт апелляция, новую версию прислать нельзя",
    "AppealTextError": "опишите, с чем не согласны: от 10 до 2000 символов",
    "InvalidSchemeError": (
        "разбалловка вида 1:3, 2:5 — задачи по порядку, баллы больше нуля"
    ),
    "BdzLockedError": "работы уже сдают — разбалловку и файлы менять нельзя",
    "BdzNotFoundError": "БДЗ не найдено",
    "NotYourBdzError": "это БДЗ не вашей группы",
}


_APPEAL = {
    "not_published": "апелляция доступна только на опубликованную оценку",
    "already_appealed": "апелляция уже подана",
    "too_late": "срок апелляции прошёл",
    "teacher_final": "оценку преподавателя оспорить нельзя",
}


def _reason(error: Exception) -> str:
    if isinstance(error, AppealNotAllowedError):
        return _APPEAL[error.reason]
    name = type(error).__name__
    if name in _REASONS:
        return _REASONS[name]
    if isinstance(error, ValueError):
        return "проверьте введённое значение"
    return "действие запрещено"
