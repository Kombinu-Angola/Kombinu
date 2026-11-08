from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.utils import extend_schema, OpenApiResponse
from .authentication import REVOKED_MESSAGE, issued_before_password_change
from .models import CustomUser
from .institutional import authenticate_institutional
from .serializers import (
    InstitutionalLoginSerializer,
    LoginResponseSerializer,
    PasswordChangeSerializer,
    TokenPairResponseSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
)
from .throttles import (
    InstitutionalLoginIdentifierRateThrottle,
    LoginIdentifierRateThrottle,
    LoginRateThrottle,
    PasswordChangeRateThrottle,
    RegisterRateThrottle,
)


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [RegisterRateThrottle]

    @extend_schema(
        summary="Registrar novo usuário",
        description="Cria uma nova conta de usuário com email e senha.",
        request=UserRegistrationSerializer,
        responses={
            201: OpenApiResponse(
                response={
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "example": "User created successfuly.",
                        },
                        "user_id": {
                            "type": "string",
                            "format": "uuid",
                            "example": "a1b2c3d4-e5f6-7890-g1h2-i3j4k5l6m7n8",
                        },
                        "email": {
                            "type": "string",
                            "format": "email",
                            "example": "user@example.com",
                        },
                    },
                },
                description="Usuário criado com sucesso",
            ),
            400: OpenApiResponse(
                response={
                    "type": "object",
                    "properties": {
                        "email": {
                            "type": "array",
                            "items": {"type": "string"},
                            "example": ["Enter a valid email address."],
                        },
                        "password": {
                            "type": "array",
                            "items": {"type": "string"},
                            "example": ["This field may not be blank."],
                        },
                    },
                },
                description="Dados de registro inválidos",
            ),
        },
        tags=["Autenticação"],
    )
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    "message": "User created successfuly.",
                    "user_id": str(user.id),
                    "email": user.email,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


INVALID_CREDENTIALS = {"error": "Invalid credentials."}

_INVALID_CREDENTIALS_RESPONSE = OpenApiResponse(
    response={
        "type": "object",
        "properties": {"error": {"type": "string", "example": "Invalid credentials."}},
    },
    description="Credenciais inválidas",
)


def login_response(user):
    refresh = RefreshToken.for_user(user)
    return Response(
        {
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "user": UserProfileSerializer(user).data,
        },
        status=status.HTTP_200_OK,
    )


class LoginView(APIView):
    # Sem autenticação: um Bearer expirado no pedido não pode impedir o login.
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle, LoginIdentifierRateThrottle]

    @extend_schema(
        summary="Autenticar usuário",
        description=(
            "Login por email e password. Devolve tokens JWT e o perfil, com "
            "`memberships` (workspaces activos) e `must_change_password`."
        ),
        request={
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "format": "email",
                    "example": "user@example.com",
                },
                "password": {
                    "type": "string",
                    "format": "password",
                    "example": "securepassword123",
                },
            },
            "required": ["email", "password"],
        },
        responses={200: LoginResponseSerializer, 401: _INVALID_CREDENTIALS_RESPONSE},
        tags=["Autenticação"],
    )
    def post(self, request):
        from django.contrib.auth import authenticate

        email = request.data.get("email")
        password = request.data.get("password")
        user_instance = authenticate(request, username=email, password=password)
        if user_instance is None:
            return Response(INVALID_CREDENTIALS, status=status.HTTP_401_UNAUTHORIZED)
        return login_response(user_instance)


class InstitutionalLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle, InstitutionalLoginIdentifierRateThrottle]

    @extend_schema(
        summary="Login institucional",
        description=(
            "Login com o código da escola (`Organizacao.code`, 6 caracteres; "
            "não o UUID), o número de aluno e a password. Mesmo envelope do "
            "login por email. Qualquer falha devolve o mesmo 401."
        ),
        request=InstitutionalLoginSerializer,
        responses={200: LoginResponseSerializer, 401: _INVALID_CREDENTIALS_RESPONSE},
        tags=["Autenticação"],
    )
    def post(self, request):
        serializer = InstitutionalLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(INVALID_CREDENTIALS, status=status.HTTP_401_UNAUTHORIZED)
        data = serializer.validated_data
        user = authenticate_institutional(
            data["school_code"], data["student_code"], data["password"]
        )
        if user is None:
            return Response(INVALID_CREDENTIALS, status=status.HTTP_401_UNAUTHORIZED)
        return login_response(user)


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [PasswordChangeRateThrottle]
    # Única view acessível enquanto a troca obrigatória está pendente (D6).
    password_change_exempt = True

    @extend_schema(
        summary="Trocar password",
        description=(
            "Troca a password da conta autenticada (obrigatória no 1.º acesso "
            "das contas institucionais). Devolve tokens novos; os anteriores "
            "deixam de valer."
        ),
        request=PasswordChangeSerializer,
        responses={
            200: TokenPairResponseSerializer,
            400: OpenApiResponse(
                description=(
                    "Erros por campo em `current_password` (errada) ou "
                    "`new_password` (igual à actual ou recusada pelos validators)."
                )
            ),
        },
        tags=["Autenticação"],
    )
    def post(self, request):
        user = request.user
        serializer = PasswordChangeSerializer(data=request.data, context={"user": user})
        serializer.is_valid(raise_exception=True)
        user.set_password(serializer.validated_data["new_password"])
        user.must_change_password = False
        user.temp_password_expires_at = None
        # Grava password e password_changed_at juntos (revoga as sessões).
        user.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {"access_token": str(refresh.access_token), "refresh_token": str(refresh)},
            status=status.HTTP_200_OK,
        )


class PasswordAwareTokenRefreshView(TokenRefreshView):
    """
    Recebe um refresh token e devolve um novo access token. Responde 401
    (`token_not_valid`) se o refresh token foi emitido antes da última troca
    de password da conta.
    """

    def post(self, request, *args, **kwargs):
        raw = request.data.get("refresh")
        if isinstance(raw, str):
            try:
                refresh = RefreshToken(raw)
            except TokenError:
                refresh = None  # o caminho normal devolve o erro habitual
            if refresh is not None:
                user = CustomUser.objects.filter(
                    **{jwt_settings.USER_ID_FIELD: refresh.payload.get(jwt_settings.USER_ID_CLAIM)}
                ).first()
                if user is not None and issued_before_password_change(user, refresh):
                    raise InvalidToken(REVOKED_MESSAGE)
        return super().post(request, *args, **kwargs)


from apps.contents.models import Content
from apps.quizzes.models import QuizSubmission
from apps.rankings import selectors as xp
from apps.tenancy.scoping import WorkspaceScopedMixin


class LearnerStatsView(WorkspaceScopedMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Get Learner Stats", tags=["Dashboard"])
    def get(self, request):
        user = request.user
        organizacao = self.workspace
        submissions = QuizSubmission.objects.for_context(organizacao).filter(user=user)

        courses_completed = submissions.values('quiz__content').distinct().count()
        quizzes_taken = submissions.count()
        # Pontos: XP ganho neste workspace (XPEvent). O nível é da carteira
        # global do utilizador (um só histórico de XP entre workspaces).
        total_points = xp.xp_total(user, organizacao)
        current_level = xp.level_for(xp.xp_total(user))
        
        return Response({
            "coursesCompleted": courses_completed,
            "totalPoints": total_points,
            "currentLevel": current_level,
            "quizzesTaken": quizzes_taken
        })

class LearnerCoursesView(WorkspaceScopedMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Get Enrolled Courses", tags=["Dashboard"])
    def get(self, request):
        user = request.user

        submissions = (
            QuizSubmission.objects
            .for_context(self.workspace)
            .filter(user=user)
            .select_related("quiz__content")
            .order_by("-submitted_at")
        )

        seen = set()
        data = []
        for submission in submissions:
            content = submission.quiz.content
            if content.id in seen:
                continue
            seen.add(content.id)
            data.append({
                "id": str(content.id),
                "title": content.title,
                "progress": 100,
                "lastAccessed": submission.submitted_at.strftime("%Y-%m-%d"),
                "thumbnail": content.thumbnail or "https://placehold.co/500x300?text=Kombinu",
            })

        return Response(data)

class CreatorStatsView(WorkspaceScopedMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Get Creator Stats", tags=["Dashboard"])
    def get(self, request):
        user = request.user
        organizacao = self.workspace
        created_contents = Content.objects.for_context(organizacao).filter(creator=user)
        total_courses = created_contents.count()

        # totalStudents: unique users who took quizzes on my content (neste workspace)
        total_students = (
            QuizSubmission.objects.for_context(organizacao)
            .filter(quiz__content__creator=user)
            .values('user')
            .distinct()
            .count()
        )
        
        return Response({
            "totalStudents": total_students,
            "totalCourses": total_courses,
            "averageRating": 0,
            "totalRevenue": 0
        })
