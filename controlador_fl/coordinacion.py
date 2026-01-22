import math
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple


# ---------------------------------------------------------------------------
# Utilidades geométricas
# ---------------------------------------------------------------------------

def haversine(lat1, lon1, lat2, lon2) -> float:
    """
    Distancia en metros entre dos puntos GPS.
    """
    R = 6371e3
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ---------------------------------------------------------------------------
# Modelos de datos
# ---------------------------------------------------------------------------

@dataclass
class Semaforo:
    """
    Semáforo físico en una vía, identificado por índice local.
    """
    id_local: int
    lat: float
    lon: float


@dataclass
class TramoVelocidad:
    """
    Tramo de velocidad de diseño sobre una vía.

    - i_inicio, i_fin: índices de semáforos entre los cuales aplica Vd.
    - vd_kmh: velocidad de diseño en km/h.
    """
    i_inicio: int
    i_fin: int
    vd_kmh: float


@dataclass
class TramoCoordinacion:
    """
    Resultado de coordinación para un tramo entre semáforos i -> j.
    """
    via_id: str           # "V1" o "V2"
    i: int                # índice semáforo inicio
    j: int                # índice semáforo fin
    dist_m: float         # distancia en metros
    vd_kmh: float         # velocidad diseño usada (km/h)
    offset_s: float       # O_i = D_i / Vd_i en segundos
    tiempo_viaje_s: float # igual a offset_s para vehículo a Vd


@dataclass
class PlanCoordinacion:
    """
    Plan global para una vía:
    - tramos: lista de TramoCoordinacion
    - ciclo_base_s: ciclo C base (segundos)
    - banda_objetivo_s: ancho de banda objetivo (segundos)
    """
    via_id: str
    tramos: List[TramoCoordinacion]
    ciclo_base_s: float
    banda_objetivo_s: float


# ---------------------------------------------------------------------------
# Funciones de cálculo
# ---------------------------------------------------------------------------

def asignar_vd_a_tramo(idx: int,
                       tramos_vd: List[TramoVelocidad],
                       vd_default_kmh: float) -> float:
    """
    Dado un tramo entre semáforos idx -> idx+1, busca qué velocidad de diseño
    le corresponde según la tabla de TramoVelocidad. Si no coincide ningún
    tramo específico, usa vd_default_kmh.
    """
    for tv in tramos_vd:
        if tv.i_inicio <= idx < tv.i_fin:
            return tv.vd_kmh
    return vd_default_kmh


def construir_tramos_coordinacion(via_id: str,
                                  semaforos: List[Semaforo],
                                  tramos_vd: List[TramoVelocidad],
                                  vd_default_kmh: float) -> List[TramoCoordinacion]:
    """
    Construye la lista de TramoCoordinacion (distancias, Vd, offsets) para una vía.

    - via_id: "V1" o "V2".
    - semaforos: lista ordenada en el sentido de circulación.
    - tramos_vd: definición de Vd por rango de índices de semáforos.
    - vd_default_kmh: velocidad por defecto si ningún tramo coincide.
    """
    if len(semaforos) < 2:
        return []

    tramos: List[TramoCoordinacion] = []

    for idx in range(len(semaforos) - 1):
        s_i = semaforos[idx]
        s_j = semaforos[idx + 1]

        dist_m = haversine(s_i.lat, s_i.lon, s_j.lat, s_j.lon)

        vd_kmh = asignar_vd_a_tramo(idx, tramos_vd, vd_default_kmh)
        vd_ms = vd_kmh * 1000.0 / 3600.0
        if vd_ms <= 0:
            vd_ms = 0.1  # evita división por cero

        offset_s = dist_m / vd_ms
        tiempo_viaje_s = offset_s

        tramos.append(
            TramoCoordinacion(
                via_id=via_id,
                i=s_i.id_local,
                j=s_j.id_local,
                dist_m=dist_m,
                vd_kmh=vd_kmh,
                offset_s=offset_s,
                tiempo_viaje_s=tiempo_viaje_s
            )
        )

    return tramos


def estimar_ciclo_webster(flujos_criticos: List[float],
                          lost_time_s: float = 12.0) -> float:
    """
    Estima un ciclo base usando una forma simplificada de la fórmula de Webster:

        C0 = (1.5*L + 5) / (1 - y)

    donde:
        L = lost_time_s (tiempo perdido por ciclo, rojos y amarillos)
        y = sumatoria de flujos críticos (ratio v/sat) por fase.

    Si no hay datos de flujo, se usa un y moderado (0.6). [web:138][web:139]
    """
    if flujos_criticos:
        y = sum(flujos_criticos)
        y = min(max(y, 0.2), 0.9)
    else:
        y = 0.6

    if y >= 1.0:
        y = 0.9

    C0 = (1.5 * lost_time_s + 5.0) / (1.0 - y)
    C0 = max(40.0, min(C0, 140.0))
    return C0


def calcular_banda_objetivo(ciclo_s: float,
                            porcentaje: float = 0.45) -> float:
    """
    Calcula una banda objetivo B en segundos como porcentaje del ciclo C.
    Por defecto, 45% del ciclo. [web:124]
    """
    porcentaje = max(0.3, min(porcentaje, 0.7))
    return ciclo_s * porcentaje


def generar_plan_para_via(via_id: str,
                          semaforos: List[Semaforo],
                          tramos_vd: List[TramoVelocidad],
                          vd_default_kmh: float,
                          flujos_criticos: List[float] = None,
                          lost_time_s: float = 12.0,
                          banda_porcentaje: float = 0.45) -> PlanCoordinacion:
    """
    Genera un PlanCoordinacion para una vía:

    - Construye tramos con distancias, Vd y offsets.
    - Calcula un ciclo base C0 (Webster simplificado).
    - Define banda objetivo B.

    La lógica difusa posterior ajustará C y offsets sobre este plan base.
    """
    tramos = construir_tramos_coordinacion(
        via_id=via_id,
        semaforos=semaforos,
        tramos_vd=tramos_vd,
        vd_default_kmh=vd_default_kmh
    )

    ciclo_base_s = estimar_ciclo_webster(
        flujos_criticos=flujos_criticos or [],
        lost_time_s=lost_time_s
    )

    banda_objetivo_s = calcular_banda_objetivo(
        ciclo_s=ciclo_base_s,
        porcentaje=banda_porcentaje
    )

    return PlanCoordinacion(
        via_id=via_id,
        tramos=tramos,
        ciclo_base_s=ciclo_base_s,
        banda_objetivo_s=banda_objetivo_s
    )


# ---------------------------------------------------------------------------
# Función de alto nivel para ambas vías
# ---------------------------------------------------------------------------

def generar_plan_global(
    via1_semaforos: List[Dict],
    via2_semaforos: List[Dict],
    via1_tramos_vd: List[Dict],
    via2_tramos_vd: List[Dict],
    vd_default_via1_kmh: float = 40.0,
    vd_default_via2_kmh: float = 40.0,
    flujos_criticos_via1: List[float] = None,
    flujos_criticos_via2: List[float] = None,
    lost_time_s: float = 12.0,
    banda_porcentaje: float = 0.45
) -> Dict[str, Dict]:
    """
    Punto de entrada pensado para tu GUI.

    Recibe datos sencillos (dicts) que podés extraer de semaforos_rn3.yaml:

        via1_semaforos = [{"id":0,"lat":..,"lon":..}, ...]
        via1_tramos_vd = [{"i_inicio":0,"i_fin":3,"vd_kmh":40.0}, ...]

    Devuelve un dict:

        {
          "V1": {
             "via_id": "V1",
             "ciclo_base_s": ...,
             "banda_objetivo_s": ...,
             "tramos": [ {...}, {...}, ... ]
          },
          "V2": { ... }
        }

    que tu GUI puede mostrar en la pestaña de tiempos, y que luego la lógica
    difusa puede usar como plan base.
    """

    # convertir a objetos
    sem_v1 = [
        Semaforo(id_local=s["id"], lat=s["lat"], lon=s["lon"])
        for s in via1_semaforos
    ]
    sem_v2 = [
        Semaforo(id_local=s["id"], lat=s["lat"], lon=s["lon"])
        for s in via2_semaforos
    ]

    tramos_v1 = [
        TramoVelocidad(i_inicio=t["i_inicio"], i_fin=t["i_fin"], vd_kmh=t["vd_kmh"])
        for t in via1_tramos_vd
    ]
    tramos_v2 = [
        TramoVelocidad(i_inicio=t["i_inicio"], i_fin=t["i_fin"], vd_kmh=t["vd_kmh"])
        for t in via2_tramos_vd
    ]

    plan_v1 = generar_plan_para_via(
        via_id="V1",
        semaforos=sem_v1,
        tramos_vd=tramos_v1,
        vd_default_kmh=vd_default_via1_kmh,
        flujos_criticos=flujos_criticos_via1,
        lost_time_s=lost_time_s,
        banda_porcentaje=banda_porcentaje
    )

    plan_v2 = generar_plan_para_via(
        via_id="V2",
        semaforos=sem_v2,
        tramos_vd=tramos_v2,
        vd_default_kmh=vd_default_via2_kmh,
        flujos_criticos=flujos_criticos_via2,
        lost_time_s=lost_time_s,
        banda_porcentaje=banda_porcentaje
    )

    return {
        "V1": {
            "via_id": plan_v1.via_id,
            "ciclo_base_s": plan_v1.ciclo_base_s,
            "banda_objetivo_s": plan_v1.banda_objetivo_s,
            "tramos": [asdict(t) for t in plan_v1.tramos]
        },
        "V2": {
            "via_id": plan_v2.via_id,
            "ciclo_base_s": plan_v2.ciclo_base_s,
            "banda_objetivo_s": plan_v2.banda_objetivo_s,
            "tramos": [asdict(t) for t in plan_v2.tramos]
        }
    }


# ---------------------------------------------------------------------------
# Ejemplo de uso básico (para pruebas unitarias, no GUI)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Ejemplo mínimo con 3 semáforos por vía y un tramo de Vd único.
    via1_semaforos = [
        {"id": 0, "lat": -45.8700, "lon": -67.5000},
        {"id": 1, "lat": -45.8690, "lon": -67.4950},
        {"id": 2, "lat": -45.8680, "lon": -67.4900},
    ]
    via2_semaforos = [
        {"id": 0, "lat": -45.8680, "lon": -67.4900},
        {"id": 1, "lat": -45.8690, "lon": -67.4950},
        {"id": 2, "lat": -45.8700, "lon": -67.5000},
    ]

    via1_tramos_vd = [
        {"i_inicio": 0, "i_fin": 2, "vd_kmh": 40.0}
    ]
    via2_tramos_vd = [
        {"i_inicio": 0, "i_fin": 2, "vd_kmh": 40.0}
    ]

    plan = generar_plan_global(
        via1_semaforos=via1_semaforos,
        via2_semaforos=via2_semaforos,
        via1_tramos_vd=via1_tramos_vd,
        via2_tramos_vd=via2_tramos_vd,
        vd_default_via1_kmh=40.0,
        vd_default_via2_kmh=40.0
    )

    import pprint
    pprint.pp(plan)