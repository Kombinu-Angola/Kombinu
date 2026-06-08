from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiResponse
from .serializers import UserProfileSerializer, UserRegistrationSerializer


class RegisterView(APIView):
    permission_classes = []

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


class LoginView(APIView):
    permission_classes = []

    @extend_schema(
        summary="Autenticar usuário",
        description="Realiza login do usuário e retorna tokens JWT de acesso e refresh.",
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
        responses={
            200: OpenApiResponse(
                response={
                    "type": "object",
                    "properties": {
                        "access_token": {
                            "type": "string",
                            "example": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                        },
                        "refresh_token": {
                            "type": "string",
                            "example": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                        },
                        "user": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer", "example": 1},
                                "email": {
                                    "type": "string",
                                    "format": "email",
                                    "example": "user@example.com",
                                },
                                "first_name": {"type": "string", "example": "João"},
                                "last_name": {"type": "string", "example": "Silva"},
                                "date_joined": {
                                    "type": "string",
                                    "format": "date-time",
                                    "example": "2023-01-01T10:00:00Z",
                                },
                            },
                        },
                    },
                },
                description="Login realizado com sucesso",
            ),
            401: OpenApiResponse(
                response={
                    "type": "object",
                    "properties": {
                        "error": {"type": "string", "example": "Invalid credentials."}
                    },
                },
                description="Credenciais inválidas",
            ),
        },
        tags=["Autenticação"],
    )
    def post(self, request):
        from django.contrib.auth import authenticate

        email = request.data.get("email")
        password = request.data.get("password")
        user_instance = authenticate(request, username=email, password=password)
        if user_instance is not None:
            refresh = RefreshToken.for_user(user_instance)
            user_serializer = UserProfileSerializer(user_instance)
            return Response(
                {
                    "access_token": str(refresh.access_token),
                    "refresh_token": str(refresh),
                    "user": user_serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {"error": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED
            )


from rest_framework.permissions import IsAuthenticated
from apps.contents.models import Content
from apps.quizzes.models import QuizSubmission
from django.db.models import Sum

class LearnerStatsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Get Learner Stats", tags=["Dashboard"])
    def get(self, request):
        user = request.user
        submissions = QuizSubmission.objects.filter(user=user)
        
        courses_completed = submissions.values('quiz__content').distinct().count()
        total_points = submissions.aggregate(Sum('score'))['score__sum'] or 0
        quizzes_taken = submissions.count()
        current_level = (total_points // 1000) + 1
        
        return Response({
            "coursesCompleted": courses_completed,
            "totalPoints": total_points,
            "currentLevel": current_level,
            "quizzesTaken": quizzes_taken
        })

class LearnerCoursesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Get Enrolled Courses", tags=["Dashboard"])
    def get(self, request):
        user = request.user

        submissions = (
            QuizSubmission.objects
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

class CreatorStatsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Get Creator Stats", tags=["Dashboard"])
    def get(self, request):
        user = request.user
        created_contents = Content.objects.filter(creator=user)
        total_courses = created_contents.count()
        
        # totalStudents: unique users who took quizzes on my content
        total_students = QuizSubmission.objects.filter(quiz__content__creator=user).values('user').distinct().count()
        
        return Response({
            "totalStudents": total_students,
            "totalCourses": total_courses,
            "averageRating": 0,
            "totalRevenue": 0
        })
