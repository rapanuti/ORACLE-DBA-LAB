"""Generador determinista de datos FICTICIOS para el esquema de citas médicas."""
from __future__ import annotations

import datetime as dt
import hashlib
import random

NOMBRES_F = ["Ana", "Lucía", "María", "Sofía", "Valentina", "Camila", "Isabel", "Elena", "Paula",
             "Daniela", "Gabriela", "Laura", "Carmen", "Rosa", "Andrea", "Natalia", "Mariana",
             "Julia", "Teresa", "Beatriz"]
NOMBRES_M = ["Carlos", "José", "Luis", "Miguel", "Andrés", "Diego", "Javier", "Pedro", "Pablo",
             "Jorge", "Manuel", "Ricardo", "Fernando", "Alejandro", "Tomás", "Rafael", "Sergio",
             "Martín", "Hugo", "Raúl"]
APELLIDOS = ["García", "Rodríguez", "Martínez", "López", "González", "Pérez", "Sánchez", "Ramírez",
             "Torres", "Flores", "Rivera", "Gómez", "Díaz", "Morales", "Ortiz", "Castillo", "Romero",
             "Vargas", "Herrera", "Medina", "Castro", "Suárez", "Rojas", "Mendoza", "Silva",
             "Navarro", "Molina", "Delgado", "Guerrero", "Vega"]
CIUDADES = ["Bogotá", "Caracas", "Lima", "Quito", "Madrid", "Valencia", "Medellín", "Maracaibo",
            "Santiago", "Ciudad de México"]
SEGUROS = ["Ninguno", "SaludTotal", "VidaPlus", "MediCare Demo", "Seguros Andinos"]
CALLES = ["Av. Principal", "Calle 10", "Carrera 7", "Av. Libertador", "Calle Real", "Paseo del Río"]

ESPECIALIDADES = [
    ("Medicina General", "Atención primaria y prevención", 40),
    ("Cardiología", "Corazón y sistema circulatorio", 95),
    ("Pediatría", "Atención a niños y adolescentes", 55),
    ("Dermatología", "Piel, cabello y uñas", 70),
    ("Ginecología", "Salud reproductiva femenina", 75),
    ("Traumatología", "Huesos, músculos y articulaciones", 85),
    ("Neurología", "Sistema nervioso", 110),
    ("Oftalmología", "Ojos y visión", 65),
    ("Psiquiatría", "Salud mental", 90),
    ("Endocrinología", "Hormonas y metabolismo", 80),
]
MOTIVOS = ["Control rutinario", "Dolor de cabeza", "Revisión de resultados", "Dolor articular",
           "Chequeo anual", "Seguimiento de tratamiento", "Erupción cutánea", "Fiebre persistente",
           "Control de presión arterial", "Revisión postoperatoria", "Ansiedad", "Visión borrosa"]
DIAGNOSTICOS = [("J06.9", "Infección aguda de vías respiratorias superiores", "Reposo, hidratación y paracetamol"),
                ("I10", "Hipertensión esencial", "Enalapril 10 mg y dieta baja en sodio"),
                ("M54.5", "Lumbalgia", "Fisioterapia e ibuprofeno"),
                ("L20.9", "Dermatitis atópica", "Crema hidratante y corticoide tópico"),
                ("E11.9", "Diabetes mellitus tipo 2", "Metformina 850 mg y control de glucosa"),
                ("G43.9", "Migraña", "Sumatriptán según necesidad"),
                ("H52.1", "Miopía", "Lentes correctivos"),
                ("F41.1", "Trastorno de ansiedad generalizada", "Terapia cognitivo-conductual"),
                ("Z00.0", "Examen médico general", "Sin tratamiento"),
                ("K21.9", "Reflujo gastroesofágico", "Omeprazol 20 mg")]
ROLES = [("ADMIN", "Administrador del sistema"), ("MEDICO", "Personal médico"),
         ("RECEPCION", "Agenda y recepción de pacientes"), ("FACTURACION", "Gestión de pagos")]


def _strip(s: str) -> str:
    return (s.lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o")
            .replace("ú", "u").replace("ñ", "n").replace(" ", ""))


def generate(today: dt.date | None = None, seed: int = 2024) -> dict[str, list[tuple]]:
    rnd = random.Random(seed)
    today = today or dt.date.today()
    data: dict[str, list[tuple]] = {}

    data["roles"] = [(i + 1, n, d) for i, (n, d) in enumerate(ROLES)]
    data["especialidades"] = [(i + 1, n, d, t) for i, (n, d, t) in enumerate(ESPECIALIDADES)]

    usuarios, usuario_roles, medicos = [], [], []
    for i in range(1, 26):  # 25 médicos, cada uno con usuario
        sexo_f = rnd.random() < 0.5
        nom = rnd.choice(NOMBRES_F if sexo_f else NOMBRES_M)
        ape = f"{rnd.choice(APELLIDOS)} {rnd.choice(APELLIDOS)}"
        user = f"dr.{_strip(nom)}{i}"
        usuarios.append((i, user, f"{user}@clinica-demo.test",
                         hashlib.sha256(user.encode()).hexdigest(), "S",
                         today - dt.timedelta(days=rnd.randint(200, 2000))))
        usuario_roles.append((i, 2))
        esp = (i - 1) % len(ESPECIALIDADES) + 1
        medicos.append((i, nom, ape, f"COL-{10000 + i * 37}", esp, f"{user}@clinica-demo.test",
                        f"+00 555 {rnd.randint(1000000, 9999999)}",
                        today - dt.timedelta(days=rnd.randint(200, 5000)),
                        "N" if i in (7, 19) else "S", i))
    staff = [("admin", 1), ("recepcion1", 3), ("recepcion2", 3), ("caja1", 4), ("auditor", 1)]
    for j, (u, r) in enumerate(staff, start=26):
        usuarios.append((j, u, f"{u}@clinica-demo.test", hashlib.sha256(u.encode()).hexdigest(),
                         "S", today - dt.timedelta(days=rnd.randint(100, 900))))
        usuario_roles.append((j, r))
    usuario_roles.append((26, 4))
    data["usuarios"], data["usuario_roles"], data["medicos"] = usuarios, usuario_roles, medicos

    consultorios = []
    for i in range(1, 16):
        edificio = "Torre A" if i <= 8 else "Torre B"
        consultorios.append((i, f"{edificio[-1]}-{(i - 1) % 8 // 3 + 1}{i:02d}", (i - 1) % 8 // 3 + 1,
                             edificio, "N" if i in (5, 13) else "S"))
    data["consultorios"] = consultorios

    pacientes = []
    for i in range(1, 301):
        sexo = rnd.choices(["F", "M", "O"], weights=[49, 49, 2])[0]
        nom = rnd.choice(NOMBRES_F if sexo == "F" else NOMBRES_M if sexo == "M" else NOMBRES_F + NOMBRES_M)
        ape = f"{rnd.choice(APELLIDOS)} {rnd.choice(APELLIDOS)}"
        nac = dt.date(rnd.randint(1940, 2020), rnd.randint(1, 12), rnd.randint(1, 28))
        email = None if rnd.random() < 0.1 else f"{_strip(nom)}.{_strip(ape.split()[0])}{i}@correo-demo.test"
        registro = today - dt.timedelta(days=rnd.randint(200, 1500)) if i <= 288 else today - dt.timedelta(days=rnd.randint(1, 20))
        pacientes.append((i, f"DOC{700000 + i * 13}", nom, ape, nac, sexo, email,
                          f"+00 600 {rnd.randint(100000, 999999)}",
                          f"{rnd.choice(CALLES)} #{rnd.randint(1, 300)}", rnd.choice(CIUDADES),
                          rnd.choice(SEGUROS), registro))
    data["pacientes"] = pacientes

    # Citas: 1500, sin repetir (médico, hora). Los pacientes 289-300 (recién registrados) no tienen citas.
    citas, ocupado = [], set()
    activos = [m[0] for m in medicos if m[8] == "S"]
    cid = 0
    while len(citas) < 1500:
        dias = rnd.randint(-180, 30)
        dia = today + dt.timedelta(days=dias)
        if dia.weekday() == 6:
            continue
        hora = dt.datetime.combine(dia, dt.time(rnd.randint(8, 16), rnd.choice([0, 30])))
        med = rnd.choice(activos) if rnd.random() < 0.95 else rnd.choice([7, 19])
        if (med, hora) in ocupado:
            continue
        ocupado.add((med, hora))
        if dias < 0:
            estado = rnd.choices(["ATENDIDA", "CANCELADA", "NO_ASISTIO"], weights=[75, 15, 10])[0]
        elif dias == 0:
            estado = rnd.choice(["CONFIRMADA", "PROGRAMADA", "ATENDIDA"])
        else:
            estado = rnd.choices(["PROGRAMADA", "CONFIRMADA", "CANCELADA"], weights=[60, 30, 10])[0]
        cid += 1
        citas.append((cid, rnd.randint(1, 288), med, rnd.randint(1, 15), hora,
                      rnd.choice([20, 30, 30, 30, 45, 60]), rnd.choice(MOTIVOS), estado,
                      hora - dt.timedelta(days=rnd.randint(1, 30))))
    citas.sort(key=lambda c: c[4])
    citas = [(i + 1,) + c[1:] for i, c in enumerate(citas)]
    data["citas"] = citas

    tarifa = {m[0]: ESPECIALIDADES[m[4] - 1][2] for m in medicos}
    historias, pagos = [], []
    factura = 1000
    for c in citas:
        id_cita, id_pac, id_med, _, hora, _, _, estado, _ = c
        if estado == "ATENDIDA":
            cie, diag, trat = rnd.choice(DIAGNOSTICOS)
            obs = None if rnd.random() < 0.5 else f"Paciente refiere evolución {'favorable' if rnd.random() < 0.7 else 'lenta'}. Próximo control en {rnd.choice([15, 30, 60, 90])} días."
            historias.append((len(historias) + 1, id_pac, id_cita, id_med, hora.date(), cie, diag, trat, obs))
            metodo = rnd.choices(["EFECTIVO", "TARJETA", "TRANSFERENCIA", "SEGURO"], weights=[25, 40, 15, 20])[0]
            est_pago = rnd.choices(["PAGADO", "PENDIENTE", "REEMBOLSADO"], weights=[85, 12, 3])[0]
            factura += 1
            pagos.append((len(pagos) + 1, id_cita, float(tarifa[id_med]), metodo, est_pago,
                          hora.date() if est_pago != "PENDIENTE" else None,
                          f"F-{factura}" if est_pago != "PENDIENTE" else None))
        elif estado == "CONFIRMADA" and rnd.random() < 0.3:
            factura += 1
            pagos.append((len(pagos) + 1, id_cita, float(tarifa[id_med]), "TARJETA", "PAGADO",
                          (hora - dt.timedelta(days=1)).date(), f"F-{factura}"))
    data["historias_clinicas"], data["pagos"] = historias, pagos
    data["_next_factura"] = [(factura + 1,)]
    return data


INSERTS = {
    "roles": "INSERT INTO roles (id_rol, nombre, descripcion) VALUES (:1, :2, :3)",
    "especialidades": "INSERT INTO especialidades (id_especialidad, nombre, descripcion, tarifa_base) VALUES (:1, :2, :3, :4)",
    "usuarios": "INSERT INTO usuarios (id_usuario, username, email, password_hash, activo, fecha_creacion) VALUES (:1, :2, :3, :4, :5, :6)",
    "usuario_roles": "INSERT INTO usuario_roles (id_usuario, id_rol) VALUES (:1, :2)",
    "medicos": "INSERT INTO medicos (id_medico, nombres, apellidos, num_colegiado, id_especialidad, email, telefono, fecha_ingreso, activo, id_usuario) VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10)",
    "consultorios": "INSERT INTO consultorios (id_consultorio, codigo, piso, edificio, equipado) VALUES (:1, :2, :3, :4, :5)",
    "pacientes": "INSERT INTO pacientes (id_paciente, documento, nombres, apellidos, fecha_nacimiento, sexo, email, telefono, direccion, ciudad, seguro, fecha_registro) VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11, :12)",
    "citas": "INSERT INTO citas (id_cita, id_paciente, id_medico, id_consultorio, fecha_hora, duracion_min, motivo, estado, fecha_creacion) VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9)",
    "historias_clinicas": "INSERT INTO historias_clinicas (id_historia, id_paciente, id_cita, id_medico, fecha, codigo_cie10, diagnostico, tratamiento, observaciones) VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9)",
    "pagos": "INSERT INTO pagos (id_pago, id_cita, monto, metodo, estado, fecha_pago, numero_factura) VALUES (:1, :2, :3, :4, :5, :6, :7)",
}
IDENTITY_TABLES = ["roles", "especialidades", "usuarios", "medicos", "consultorios", "pacientes",
                   "citas", "historias_clinicas", "pagos"]
