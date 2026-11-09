"""B1: criação, edição, publicação e gestão de passos das Trilhas."""

from django.urls import reverse
from rest_framework import status

from apps.contents.models import Content
from apps.enquetes.models import Enquete
from apps.tenancy.models import Membership
from apps.trilhas.models import Trilha, TrilhaItem, TrilhaProgresso
from apps.trilhas.tests import TrilhaBase, make_quiz, make_user


class AutoriaBase(TrilhaBase):
    def setUp(self):
        super().setUp()
        self.other_teacher = make_user("prof2@test.com", "creator")
        Membership.objects.create(
            user=self.other_teacher, organizacao=self.org, role="teacher"
        )
        self.foreign_teacher = make_user("prof-outra@test.com", "creator")
        Membership.objects.create(
            user=self.foreign_teacher, organizacao=self.other_org, role="teacher"
        )
        self.foreign_hdr = {"HTTP_X_WORKSPACE": str(self.other_org.id)}
        self.foreign_content = Content.objects.create(
            title="Conteúdo da outra escola",
            description="d",
            creator=self.foreign_teacher,
            category="tecnologia",
            organizacao=self.other_org,
        )
        self.foreign_quiz = make_quiz(
            self.foreign_teacher, "Quiz alheio", self.other_org
        )
        self.foreign_enquete = Enquete.objects.create(
            organizacao=self.other_org,
            creator=self.foreign_teacher,
            kind="binaria",
            question="?",
            decision="d",
            trigger="fim-modulo",
            sample_target=5,
        )
        self.market_content = Content.objects.create(
            title="Marketplace",
            description="d",
            creator=self.teacher,
            category="tecnologia",
            organizacao=None,
        )

    def as_(self, user):
        self.client.force_authenticate(user)

    def create_trilha(self, user=None, hdr=None, **extra):
        self.as_(user or self.teacher)
        payload = {"title": "Nova", "subject": "Redes", **extra}
        return self.client.post(
            reverse("trilha-list"),
            payload,
            format="json",
            **(self.hdr if hdr is None else hdr),
        )

    def add_item(self, trilha, kind, target, user=None, hdr=None, **extra):
        self.as_(user or self.teacher)
        payload = {"kind": kind, "targetId": str(target.pk), **extra}
        return self.client.post(
            reverse("trilha-item-create", args=[trilha.pk]),
            payload,
            format="json",
            **(self.hdr if hdr is None else hdr),
        )

    def orders(self, trilha):
        return list(
            TrilhaItem.objects.filter(trilha=trilha)
            .order_by("order")
            .values_list("pk", "order")
        )


class TrilhaCreateTests(AutoriaBase):
    def test_teacher_creates_draft_in_workspace(self):
        r = self.create_trilha(
            headline="H", isSequential=False, finalExamId=str(self.exam.pk)
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        trilha = Trilha.objects.get(pk=r.data["id"])
        self.assertEqual(trilha.organizacao, self.org)
        self.assertEqual(trilha.creator, self.teacher)
        self.assertFalse(trilha.is_published)
        self.assertFalse(trilha.is_sequential)
        self.assertEqual(trilha.final_exam, self.exam)
        self.assertFalse(r.data["isPublished"])
        self.assertEqual(r.data["nodes"], [])

    def test_student_cannot_create(self):
        r = self.create_trilha(user=self.student)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_learner_cannot_create_in_marketplace(self):
        r = self.create_trilha(user=self.student, hdr={})
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_creator_creates_in_marketplace(self):
        r = self.create_trilha(hdr={})
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertIsNone(Trilha.objects.get(pk=r.data["id"]).organizacao)

    def test_title_and_subject_required(self):
        self.as_(self.teacher)
        r = self.client.post(reverse("trilha-list"), {}, format="json", **self.hdr)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", r.data)
        self.assertIn("subject", r.data)

    def test_cannot_send_is_published_on_create(self):
        r = self.create_trilha(is_published=True, isPublished=True)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertFalse(Trilha.objects.get(pk=r.data["id"]).is_published)


class TrilhaIsolationTests(AutoriaBase):
    """Itens e exame têm de ser do mesmo contexto da trilha (crítico)."""

    def test_foreign_final_exam_rejected_on_create(self):
        r = self.create_trilha(finalExamId=str(self.foreign_quiz.pk))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("finalExamId", r.data)
        self.assertFalse(Trilha.objects.filter(title="Nova").exists())

    def test_foreign_final_exam_rejected_on_patch(self):
        self.as_(self.teacher)
        r = self.client.patch(
            reverse("trilha-detail", args=[self.trilha.pk]),
            {"finalExamId": str(self.foreign_quiz.pk)},
            format="json",
            **self.hdr,
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.trilha.refresh_from_db()
        self.assertEqual(self.trilha.final_exam, self.exam)

    def test_items_from_other_school_rejected(self):
        before = self.orders(self.trilha)
        for kind, target in (
            ("conteudo", self.foreign_content),
            ("quiz", self.foreign_quiz),
            ("enquete", self.foreign_enquete),
        ):
            r = self.add_item(self.trilha, kind, target)
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST, kind)
            self.assertEqual(
                r.data["targetId"], ["Item não encontrado neste workspace."]
            )
        self.assertEqual(self.orders(self.trilha), before)

    def test_foreign_item_and_missing_item_give_same_error(self):
        foreign = self.add_item(self.trilha, "conteudo", self.foreign_content)
        missing = self.add_item(self.trilha, "conteudo", Trilha(pk=self.trilha.pk))
        self.assertEqual(foreign.status_code, missing.status_code)
        self.assertEqual(foreign.data, missing.data)

    def test_marketplace_item_rejected_in_school_trilha(self):
        r = self.add_item(self.trilha, "conteudo", self.market_content)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_school_item_rejected_in_marketplace_trilha(self):
        created = self.create_trilha(hdr={})
        trilha = Trilha.objects.get(pk=created.data["id"])
        r = self.add_item(trilha, "conteudo", self.read, hdr={})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        ok = self.add_item(trilha, "conteudo", self.market_content, hdr={})
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED, ok.data)

    def test_other_school_cannot_touch_trilha(self):
        url = reverse("trilha-detail", args=[self.trilha.pk])
        self.as_(self.foreign_teacher)
        for hdr in (self.foreign_hdr, {}):
            self.assertEqual(
                self.client.patch(
                    url, {"title": "x"}, format="json", **hdr
                ).status_code,
                status.HTTP_404_NOT_FOUND,
            )
            self.assertEqual(
                self.client.delete(url, **hdr).status_code, status.HTTP_404_NOT_FOUND
            )
            r = self.add_item(
                self.trilha,
                "conteudo",
                self.foreign_content,
                user=self.foreign_teacher,
                hdr=hdr,
            )
            self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        # Pelo workspace A, sem pertença: 403 do próprio X-Workspace.
        self.assertEqual(
            self.client.patch(
                url, {"title": "x"}, format="json", **self.hdr
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.trilha.refresh_from_db()
        self.assertEqual(self.trilha.title, "Redes I")

    def test_others_draft_enquete_rejected(self):
        draft = Enquete.objects.create(
            organizacao=self.org,
            creator=self.other_teacher,
            kind="binaria",
            question="?",
            decision="d",
            trigger="fim-modulo",
            sample_target=5,
            state="rascunho",
        )
        r = self.add_item(self.trilha, "enquete", draft)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


class TrilhaEditTests(AutoriaBase):
    def test_creator_patches_fields(self):
        self.as_(self.teacher)
        r = self.client.patch(
            reverse("trilha-detail", args=[self.trilha.pk]),
            {"title": "Redes II", "isSequential": False, "finalExamId": None},
            format="json",
            **self.hdr,
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.trilha.refresh_from_db()
        self.assertEqual(self.trilha.title, "Redes II")
        self.assertFalse(self.trilha.is_sequential)
        self.assertIsNone(self.trilha.final_exam)
        self.assertIsNone(r.data["finalExam"])

    def test_non_creator_gets_403_on_visible_trilha(self):
        url = reverse("trilha-detail", args=[self.trilha.pk])
        for user in (self.other_teacher, self.student):
            self.as_(user)
            self.assertEqual(
                self.client.patch(
                    url, {"title": "x"}, format="json", **self.hdr
                ).status_code,
                status.HTTP_403_FORBIDDEN,
            )
            self.assertEqual(
                self.client.delete(url, **self.hdr).status_code,
                status.HTTP_403_FORBIDDEN,
            )

    def test_others_draft_is_404(self):
        self.trilha.is_published = False
        self.trilha.save()
        self.as_(self.other_teacher)
        r = self.client.patch(
            reverse("trilha-detail", args=[self.trilha.pk]),
            {"title": "x"},
            format="json",
            **self.hdr,
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_put_not_allowed(self):
        self.as_(self.teacher)
        r = self.client.put(
            reverse("trilha-detail", args=[self.trilha.pk]),
            {"title": "x", "subject": "y"},
            format="json",
            **self.hdr,
        )
        self.assertEqual(r.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class TrilhaDeleteTests(AutoriaBase):
    def test_delete_without_progress(self):
        self.as_(self.teacher)
        r = self.client.delete(
            reverse("trilha-detail", args=[self.trilha.pk]), **self.hdr
        )
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Trilha.objects.filter(pk=self.trilha.pk).exists())
        self.assertFalse(TrilhaItem.objects.filter(trilha_id=self.trilha.pk).exists())

    def test_delete_with_progress_is_409(self):
        TrilhaProgresso.objects.create(
            user=self.student, item=self.i1, state="concluido"
        )
        self.as_(self.teacher)
        r = self.client.delete(
            reverse("trilha-detail", args=[self.trilha.pk]), **self.hdr
        )
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(Trilha.objects.filter(pk=self.trilha.pk).exists())
        self.assertEqual(TrilhaProgresso.objects.count(), 1)


class TrilhaPublishTests(AutoriaBase):
    def test_publish_requires_items(self):
        created = self.create_trilha()
        url = reverse("trilha-publish", args=[created.data["id"]])
        r = self.client.post(url, **self.hdr)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_publish_makes_visible_to_students(self):
        created = self.create_trilha()
        trilha = Trilha.objects.get(pk=created.data["id"])
        self.add_item(trilha, "conteudo", self.read)
        detail = reverse("trilha-detail", args=[trilha.pk])
        self.as_(self.student)
        self.assertEqual(self.client.get(detail, **self.hdr).status_code, 404)

        self.as_(self.teacher)
        r = self.client.post(reverse("trilha-publish", args=[trilha.pk]), **self.hdr)
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertTrue(r.data["isPublished"])
        again = self.client.post(
            reverse("trilha-publish", args=[trilha.pk]), **self.hdr
        )
        self.assertEqual(again.status_code, status.HTTP_200_OK)

        self.as_(self.student)
        self.assertEqual(self.client.get(detail, **self.hdr).status_code, 200)

    def test_only_creator_publishes(self):
        self.as_(self.other_teacher)
        r = self.client.post(
            reverse("trilha-publish", args=[self.trilha.pk]), **self.hdr
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class TrilhaItemTests(AutoriaBase):
    def test_add_item_appends_with_metadata(self):
        r = self.add_item(
            self.trilha,
            "quiz",
            self.exam,
            titleOverride="Revisão",
            minutes=12,
            xpReward=30,
            summary="s",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        item = TrilhaItem.objects.get(trilha=self.trilha, quiz=self.exam)
        self.assertEqual(item.order, 5)
        self.assertEqual(item.title_override, "Revisão")
        self.assertEqual(item.xp_reward, 30)
        self.assertEqual(r.data["nodes"][-1]["title"], "Revisão")

    def test_add_item_validates_kind(self):
        r = self.add_item(self.trilha, "video", self.read)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_item_metadata(self):
        self.as_(self.teacher)
        r = self.client.patch(
            reverse("trilha-item-detail", args=[self.trilha.pk, self.i1.pk]),
            {"titleOverride": "Intro", "minutes": 3},
            format="json",
            **self.hdr,
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.i1.refresh_from_db()
        self.assertEqual((self.i1.title_override, self.i1.minutes), ("Intro", 3))

    def test_item_of_another_trilha_is_404(self):
        other = Trilha.objects.create(
            organizacao=self.org, creator=self.teacher, title="Outra", subject="x"
        )
        self.as_(self.teacher)
        r = self.client.delete(
            reverse("trilha-item-detail", args=[other.pk, self.i1.pk]), **self.hdr
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(TrilhaItem.objects.filter(pk=self.i1.pk).exists())

    def test_remove_item_compacts_order(self):
        self.as_(self.teacher)
        r = self.client.delete(
            reverse("trilha-item-detail", args=[self.trilha.pk, self.i2.pk]), **self.hdr
        )
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            self.orders(self.trilha),
            [(self.i1.pk, 1), (self.i3.pk, 2), (self.i4.pk, 3)],
        )

    def test_remove_item_with_progress_is_409(self):
        TrilhaProgresso.objects.create(
            user=self.student, item=self.i2, state="concluido"
        )
        self.as_(self.teacher)
        r = self.client.delete(
            reverse("trilha-item-detail", args=[self.trilha.pk, self.i2.pk]), **self.hdr
        )
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(TrilhaItem.objects.filter(pk=self.i2.pk).exists())

    def test_reorder(self):
        self.as_(self.teacher)
        new_order = [self.i4.pk, self.i1.pk, self.i3.pk, self.i2.pk]
        r = self.client.post(
            reverse("trilha-item-reorder", args=[self.trilha.pk]),
            {"itemIds": [str(i) for i in new_order]},
            format="json",
            **self.hdr,
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(
            self.orders(self.trilha), [(pk, n) for n, pk in enumerate(new_order, 1)]
        )
        self.assertEqual(
            [n["id"] for n in r.data["nodes"]], [str(i) for i in new_order]
        )

    def test_reorder_requires_full_permutation(self):
        self.as_(self.teacher)
        url = reverse("trilha-item-reorder", args=[self.trilha.pk])
        before = self.orders(self.trilha)
        foreign = TrilhaItem.objects.create(
            trilha=Trilha.objects.create(
                organizacao=self.org, creator=self.teacher, title="T", subject="s"
            ),
            order=1,
            kind="conteudo",
            content=self.read,
        )
        for ids in (
            [self.i1.pk, self.i2.pk],
            [self.i1.pk, self.i1.pk, self.i3.pk, self.i4.pk],
            [self.i1.pk, self.i2.pk, self.i3.pk, foreign.pk],
        ):
            r = self.client.post(
                url, {"itemIds": [str(i) for i in ids]}, format="json", **self.hdr
            )
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("itemIds", r.data)
        self.assertEqual(self.orders(self.trilha), before)

    def test_non_creator_cannot_manage_items(self):
        r = self.add_item(self.trilha, "conteudo", self.read, user=self.other_teacher)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.as_(self.student)
        r = self.client.post(
            reverse("trilha-item-reorder", args=[self.trilha.pk]),
            {"itemIds": [str(self.i1.pk)]},
            format="json",
            **self.hdr,
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class TrilhaArchiveTests(AutoriaBase):
    def archive(self, action="trilha-archive", user=None):
        self.as_(user or self.teacher)
        return self.client.post(reverse(action, args=[self.trilha.pk]), **self.hdr)

    def test_archive_hides_from_students_keeps_progress(self):
        TrilhaProgresso.objects.create(
            user=self.student, item=self.i1, state="concluido"
        )
        r = self.archive()
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertIsNotNone(r.data["archivedAt"])
        self.trilha.refresh_from_db()
        self.assertIsNotNone(self.trilha.archived_at)
        self.assertEqual(TrilhaProgresso.objects.count(), 1)

        self.as_(self.student)
        listed = self.client.get(reverse("trilha-list"), **self.hdr).data["results"]
        self.assertNotIn(str(self.trilha.pk), [t["id"] for t in listed])
        detail = reverse("trilha-detail", args=[self.trilha.pk])
        self.assertEqual(self.client.get(detail, **self.hdr).status_code, 404)

        self.as_(self.teacher)
        self.assertEqual(self.client.get(detail, **self.hdr).status_code, 200)

    def test_archive_is_idempotent_and_unarchive_restores(self):
        self.archive()
        self.trilha.refresh_from_db()
        first = self.trilha.archived_at
        self.archive()
        self.trilha.refresh_from_db()
        self.assertEqual(self.trilha.archived_at, first)

        r = self.archive("trilha-unarchive")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsNone(r.data["archivedAt"])
        self.as_(self.student)
        detail = reverse("trilha-detail", args=[self.trilha.pk])
        self.assertEqual(self.client.get(detail, **self.hdr).status_code, 200)

    def test_only_creator_archives(self):
        for user in (self.other_teacher, self.student):
            self.assertEqual(self.archive(user=user).status_code, 403)
        self.trilha.refresh_from_db()
        self.assertIsNone(self.trilha.archived_at)

    def test_other_school_cannot_archive(self):
        self.as_(self.foreign_teacher)
        r = self.client.post(
            reverse("trilha-archive", args=[self.trilha.pk]), **self.foreign_hdr
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
        self.trilha.refresh_from_db()
        self.assertIsNone(self.trilha.archived_at)
