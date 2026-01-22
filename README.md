# 🚦 Control Difuso de Semáforos – Onda Verde con Python y ESP32

Este proyecto implementa un **sistema inteligente de control de semáforos** basado en **lógica difusa** y conceptos básicos de **ingeniería de tránsito**, con el objetivo de mejorar la circulación vehicular y reducir tiempos de espera.

A diferencia de los sistemas tradicionales con tiempos fijos, este enfoque **se adapta dinámicamente al tráfico real**, tomando decisiones similares a las que haría una persona observando la calle.

⚠️ El proyecto está pensado como **parte de un sistema mayor**, donde este software recibe información de tráfico ya procesada por otra aplicación externa que implementa una camara IP para sensar el flujo vehicular -proximamente estare subiendo esta seccion-.

Ver en youtube: https://www.youtube.com/watch?v=AwRiFOMe59c

[![VERenYOUTUBE->>](https://i.ytimg.com/an_webp/AwRiFOMe59c/mqdefault_6s.webp?du=3000&sqp=CO2Px8sG&rs=AOn4CLDnaAE7ZYG0vDuBw41oUMKCO8ySwQ)](https://www.youtube.com/watch?v=AwRiFOMe59c)


---

## 🎯 Idea general del proyecto

En una intersección real, el tráfico **no es constante**:
- a veces hay pocos autos,
- a veces hay congestión,
- a veces una calle necesita más tiempo de paso que otra.

Este proyecto busca resolver ese problema usando:
- **Python**, que analiza variables de tráfico y toma decisiones,
- **Python**, que analiza videos y procesa el estado del trafico,
- **ESP32**, que ejecuta esas decisiones controlando los semáforos,
- **lógica difusa**, para manejar situaciones imprecisas o variables,
- **onda verde**, para favorecer el flujo continuo de vehículos.

---

## 🧠 ¿Qué es la lógica difusa?

La lógica difusa es una forma de razonamiento que **no trabaja solo con “sí” o “no”**, sino con valores intermedios.

Por ejemplo:
- el tráfico no es solo *bajo* o *alto*,
- puede ser *liviano*, *intermedio*, *pesado* o incluso *estancado*.

Esto permite que el sistema tome decisiones **más humanas y flexibles**, ideales para fenómenos reales como el tránsito urbano.

---

## 🔄 ¿Cómo se usa la lógica difusa en este proyecto?

El flujo lógico del programa es el siguiente:

### 1️⃣ Entrada de datos (estado del tránsito)
El sistema recibe información que representa el estado del tráfico:
- nivel de congestión,
- cantidad relativa de vehículos,
- tipo de tráfico presente en la zona.

Estos datos **no provienen directamente de sensores crudos**, sino que llegan **ya procesados** desde la otra aplicación de Python que esta conectada a una camara IP.

---

### 2️⃣ Fuzzificación (interpretar el tráfico)
Los valores recibidos se transforman en **conceptos lingüísticos**, como:
- tráfico liviano,
- tráfico intermedio,
- tráfico pesado,
- tráfico estancado.

Cada estado puede pertenecer parcialmente a más de una categoría, reflejando mejor la realidad.

---

### 3️⃣ Reglas difusas (criterio de decisión)
Se aplican reglas simples, similares al razonamiento humano, por ejemplo:

> *Si el tráfico es pesado o estancado, entonces extender el tiempo de luz verde.*

Estas reglas combinan múltiples variables para decidir cómo actuar sobre los semáforos.

---

### 4️⃣ Defuzzificación (decisión concreta)
La decisión difusa se convierte en valores reales:
- duración de la luz verde,
- duración del rojo,
- ajuste dinámico del ciclo del semáforo.

Estos valores son los que finalmente se envían al ESP32.

---

## 🛣️ Relación con la ingeniería de tránsito

El proyecto aplica conceptos clásicos, pero de forma adaptativa:

### 🚗 Flujo vehicular
El sistema prioriza las calles con mayor carga vehicular, evitando tiempos muertos innecesarios.

### 🌊 Onda verde
La *onda verde* busca que varios semáforos trabajen coordinados para que los vehículos puedan avanzar sin detenerse constantemente.

En este proyecto:
- no hay tiempos fijos - pero tiene una base de tiempos minimos y maximos que sse ajustan a laslegislaciones de transito,
- la coordinación surge de decisiones dinámicas,
- la lógica difusa suaviza los cambios entre estados.

---

## 📷 Aplicación complementaria (pendiente de finalizar)

Este proyecto **depende de una segunda aplicación**, actualmente en desarrollo, que cumple un rol clave:

### ¿Qué hace esa aplicación?
- Usa una **cámara IP** como sensor de tráfico.
- Mediante una aplicación en **Python**, realiza:
  - detección y conteo de vehículos,
  - análisis del flujo vehicular,
  - clasificación del tráfico en categorías como:
    - liviano,
    - intermedio,
    - pesado,
    - estancado.
- Envía ese **dato ya procesado** a este software de control difuso.

### ¿Por qué separar ambas aplicaciones?
- Permite modular el sistema.
- Facilita reemplazar o mejorar el método de detección (por ejemplo, usar IA, cámaras IP o sensores físicos).
- Mantiene la lógica difusa independiente del método de medición.

Este software de control **no cuenta vehículos directamente**, sino que **consume esa variable externa** y la incorpora como entrada adicional al modelo difuso.

---

## 🔌 Rol de Python y ESP32

- **Python**
  - recibe las variables de tráfico procesadas,
  - ejecuta la lógica difusa,
  - calcula los tiempos óptimos de los semáforos.

- **ESP32**
  - recibe las decisiones finales,
  - controla los semáforos reales o simulados,
  - actúa como interfaz entre el software y el mundo físico.

---

## ✅ ¿Por qué este enfoque es interesante?

- Se adapta al tráfico real.
- Tolera datos imprecisos o variables.
- Usa reglas simples y comprensibles.
- Permite crecimiento modular del sistema.
- Es ideal para simulación, educación y prototipos reales.

---

## 📌 En resumen

Este proyecto muestra cómo:
- la lógica difusa puede aplicarse a problemas reales,
- la ingeniería de tránsito puede beneficiarse de sistemas adaptativos,
- Python y ESP32 pueden trabajar juntos,
- un sistema urbano puede tomar decisiones razonables sin depender de cronómetros fijos.

Es una base sólida para experimentar con **control de tráfico inteligente**, **ciudades inteligentes** y **automatización urbana**.

Recuerden que este repositorio lo voy a ir actualizando a medida que vaya avanzando con las distintas partes que conforman este proyecto.
