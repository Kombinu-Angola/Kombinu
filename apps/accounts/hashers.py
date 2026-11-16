"""
Hasher de passwords (K1). Argon2id com os parâmetros mínimos da OWASP.

O `Argon2PasswordHasher` do Django usa por omissão memory_cost=102400 (cerca
de 100 MiB por hash) e parallelism=8: com dezenas de logins em simultâneo numa
instância pequena, isso esgota a RAM. 19 MiB, 2 iterações e 1 thread é a
configuração mínima recomendada pela OWASP para o Argon2id.

O algoritmo continua a chamar-se "argon2": hashes com outros parâmetros são
reconhecidos e actualizados sozinhos no login seguinte (`must_update`).
"""

from django.contrib.auth.hashers import Argon2PasswordHasher


class KombinuArgon2PasswordHasher(Argon2PasswordHasher):
    time_cost = 2
    memory_cost = 19456  # KiB, ou seja, 19 MiB
    parallelism = 1
