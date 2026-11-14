from django.db import models


class OrganizacaoQuerySet(models.QuerySet):
    """
    QuerySet para modelos com FK `organizacao` nullable (NULL = marketplace).

    `for_context(None)` devolve só o marketplace; `for_context(org)` devolve só
    os objectos dessa organização. Não há herança entre contextos: o workspace
    escolar não vê o marketplace e vice-versa (SLA §2, Ponto Cego 3).
    """

    def for_context(self, organizacao):
        return self.filter(organizacao=organizacao)
