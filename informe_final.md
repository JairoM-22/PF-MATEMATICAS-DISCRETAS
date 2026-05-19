```latex
\documentclass[12pt, a4paper]{article}

% Paquetes esenciales
\usepackage[utf8]{inputenc}
\usepackage[spanish]{babel}
\usepackage{geometry}
\usepackage{hyperref}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{graphicx}
\usepackage{algpseudocode}
\usepackage{algorithm}
\usepackage{setspace}
\usepackage{titlesec}
\usepackage{float}
\usepackage{enumitem}
\usepackage{xcolor}

% Configuración de márgenes y espaciado para optimizar lectura (y volumen)
\geometry{top=2.5cm, bottom=2.5cm, left=3cm, right=3cm}
\onehalfspacing

% Configuración de colores para enlaces
\hypersetup{
    colorlinks=true,
    linkcolor=blue,
    filecolor=magenta,      
    urlcolor=blue,
    pdftitle={Informe Final - Matemáticas Discretas},
}

\begin{document}

\begin{titlepage}
    \centering
    \vspace*{1.5cm}
    
    {\scshape\LARGE \textbf{Universidad del Norte} \par}
    \vspace{0.5cm}
    {\scshape\Large Programa de Ingeniería de Sistemas \par}
    \vspace{2.5cm}
    
    \hrule height 1.5pt
    \vspace{0.5cm}
    {\huge\bfseries Informe Final: Optimización de Rutas en el Sistema Transmetro mediante la Teoría de Grafos\par}
    \vspace{0.5cm}
    \hrule height 1.5pt
    \vspace{3cm}
    
    {\Large \textbf{Proyecto Final - Matemáticas Discretas} \par}
    \vspace{0.5cm}
    {\large NRC: 2223 \par}
    {\large Semestre: 2026-I \par}
    
    \vspace{3cm}
    
    \begin{flushleft} \large
        \textbf{Autores:}\\
        Juan Esteban Contreras\\
        Santiago Molina\\
        Jairo Molina\\
        Santiago Barrios\\
    \end{flushleft}
    
    \vspace{1.5cm}
    
    \begin{flushleft} \large
        \textbf{Profesora:} \\
        Diana Mejía
    \end{flushleft}
    
    \vfill
    
    {\large \textbf{Fecha de entrega:} 14 de mayo de 2026 \par}
\end{titlepage}

\newpage
\tableofcontents
\newpage

\section{Planteamiento del problema}

La movilidad urbana es uno de los pilares fundamentales para el desarrollo socioeconómico de cualquier ciudad metropolitana. En el caso específico de Barranquilla, el sistema de transporte masivo Transmetro representa la principal arteria de desplazamiento para miles de ciudadanos que necesitan movilizarse diariamente hacia sus lugares de trabajo, estudio u ocio. A pesar de contar con una estructura de rutas definidas, estaciones y horarios (estandarizados mediante el formato internacional General Transit Feed Specification o GTFS), los usuarios frecuentemente se enfrentan a un desafío no trivial: la toma de decisiones al elegir una ruta de transporte.

El problema radica en que encontrar la ruta "óptima" entre dos puntos de la ciudad no siempre significa encontrar la ruta geográficamente más corta. El concepto de optimización en el transporte público es multidimensional y depende de factores como la distancia física, el tiempo estimado de llegada y, de forma crítica para muchos usuarios, el impacto económico o costo monetario del viaje. 

En Transmetro, la estructura tarifaria establece que con un solo pasaje (cuyo valor actual es de \$3.700 COP), un usuario tiene derecho a abordar hasta tres buses diferentes dentro de una ventana de tiempo, es decir, un abordaje inicial más dos transbordos gratuitos. Si un trayecto requiere tomar un cuarto bus, el sistema deduce el valor de un segundo pasaje; si se toma un séptimo, se cobra un tercero, y así sucesivamente. Adicionalmente, las transferencias o caminatas internas entre plataformas de una misma estación no contabilizan como un nuevo abordaje, lo cual añade una capa adicional de complejidad al momento de evaluar los trayectos.

Para un pasajero promedio, trazar mentalmente una ruta que minimice los costos económicos sin sacrificar exageradamente el tiempo de viaje o la distancia recorrida resulta ser una tarea agobiante. Las herramientas de navegación convencionales suelen priorizar el tiempo de llegada, sugiriendo en ocasiones rutas que implican múltiples cambios de línea que, bajo el esquema de Transmetro, podrían incurrir en el cobro de pasajes adicionales que el usuario no tenía previstos. 

Ante esta situación, el presente proyecto aborda la problemática estructurando una solución basada en conceptos matemáticos y computacionales. Se plantea la necesidad de desarrollar un sistema de enrutamiento que, utilizando la información abierta de Transmetro, construya una red interconectada capaz de calcular el camino ideal entre cualquier par de estaciones. Este algoritmo debe ofrecerle al usuario la libertad de decidir qué métrica desea optimizar: si prefiere la ruta más rápida (minimizando la distancia absoluta), o si busca la ruta más económica (garantizando el menor número de pasajes pagados posibles, usando la distancia como criterio de desempate). Resolver este problema requiere trasladar las reglas del mundo físico y comercial a una estructura formal, tarea en la cual la Teoría de Grafos y el análisis de algoritmos de caminos mínimos juegan el papel protagónico.

\newpage
\section{Modelación matemática}

Para dar solución a la búsqueda de rutas óptimas, hemos modelado la red del sistema Transmetro haciendo uso de la Teoría de Grafos. Matemáticamente, el sistema de transporte se representa mediante un grafo ponderado y no dirigido $G = (V, E)$.

\subsection{Definición de Vértices y Aristas}
Sea el conjunto de vértices $V = \{v_1, v_2, \dots, v_n\}$, donde cada vértice $v_i$ representa una parada o estación del sistema (extraída del archivo \texttt{stops.txt} del estándar GTFS). Cada nodo almacena sus coordenadas espaciales: latitud y longitud.

El conjunto de aristas $E$ está compuesto por dos subconjuntos disjuntos: $E = E_v \cup E_t$, correspondientes a los viajes y a las transferencias, respectivamente.

\begin{itemize}
    \item \textbf{Aristas de viaje ($E_v$):} Una arista $\{v_i, v_j\} \in E_v$ existe si un autobús transita de forma directa y consecutiva entre la parada $v_i$ y la parada $v_j$. Cada arista de este tipo tiene asociado un conjunto de rutas $R_{i,j}$ que indican las líneas de bus que operan dicho segmento.
    \item \textbf{Aristas de transferencia ($E_t$):} Una arista $\{v_i, v_j\} \in E_t$ existe si los nodos $v_i$ y $v_j$ pertenecen a la misma estación física (tienen el mismo \texttt{parent\_station} o nombre de parada en los datos). Representan la capacidad de caminar entre plataformas sin salir de la estación ni abordar un bus nuevo.
\end{itemize}

\subsection{Funciones de Peso}
Asignamos un peso $W(e)$ a cada arista $e \in E$, basado en la distancia física calculada mediante la fórmula del semiverseno (Haversine). Siendo $R$ el radio de la Tierra, y dadas las coordenadas $(\phi_1, \lambda_1)$ y $(\phi_2, \lambda_2)$ de los extremos de la arista, la distancia en kilómetros está dada por:
\[
W(e) = 2R \arcsin\left(\sqrt{\sin^2\left(\frac{\phi_2 - \phi_1}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\lambda_2 - \lambda_1}{2}\right)}\right)
\]
Para las aristas de transferencia $e \in E_t$, el peso físico se define como $W(e) = 0$, puesto que la caminata no influye en el cálculo de distancias de los vehículos.

\subsection{Costo Tarifario y Dijkstra Modificado}
El desafío central del modelo es la evaluación de costos monetarios. Sea un camino simple $P = (u_0, u_1, \dots, u_k)$. Definimos la función de buses tomados $B(P)$ como la cantidad de líneas distintas que el pasajero debe abordar a lo largo del camino. Un transbordo ocurre únicamente si entre aristas consecutivas de viaje la intersección de las rutas disponibles es vacía ($R_{u_{i-1}, u_i} \cap R_{u_i, u_{i+1}} = \emptyset$). 

La tarifa de Transmetro establece que $1$ pasaje permite el uso de hasta $3$ buses. Así, el número de pasajes $T(P)$ se calcula usando la función techo:
\[
T(P) = \left\lceil \frac{B(P)}{3} \right\rceil
\]
El objetivo del modo de "ahorro" es encontrar el camino $P^*$ desde un origen $s$ a un destino $t$ que minimice la función objetivo $F(P)$, donde:
\[
F(P) = \alpha \cdot T(P) + \sum_{e \in P} W(e)
\]
Para garantizar que la disminución monetaria siempre prime sobre la distancia física, elegimos una constante $\alpha = 10,000$ (una distancia ficticia inalcanzable en la red). De esta manera, cualquier camino que requiera 1 pasaje tendrá un costo muy inferior a uno que requiera 2, resolviendo el problema mediante una variante del algoritmo de Dijkstra.

\subsection{Análisis Estructural y Métricas de Centralidad}
Además del enrutamiento, el modelo permite evaluar la robustez y topología de la red mediante métricas de centralidad:
\begin{itemize}
    \item \textbf{Centralidad de Grado (Degree Centrality):} Mide la cantidad de conexiones directas de una estación.
    \item \textbf{Centralidad de Intermediación (Betweenness Centrality):} Cuantifica la frecuencia con la que un nodo actúa como puente en los caminos más cortos entre otros pares de nodos. Identifica cuellos de botella.
    \item \textbf{Centralidad de Cercanía (Closeness Centrality):} Evalúa qué tan rápido se puede llegar desde un nodo a todos los demás.
\end{itemize}
Adicionalmente, se modeló la tolerancia a fallos simulando la eliminación de vértices críticos (estaciones inoperativas) para observar si el número de componentes conexas del grafo se incrementa, lo cual indicaría una fragmentación del sistema de transporte.

\newpage
\section{Desarrollo o implementación}

La construcción e implementación del sistema se realizó bajo el entorno de programación de Python, integrando herramientas especializadas para la manipulación de datos y cálculos sobre redes. Se puede acceder al repositorio con el código fuente completo en el siguiente enlace de GitHub:
\begin{center}
    \url{https://github.com/JairoM-22/PF-MATEMATICAS-DISCRETAS}
\end{center}

\subsection{Tratamiento de Datos y Estructura del Grafo}
La información de Transmetro fue ingestada desde los archivos GTFS utilizando la librería \texttt{pandas}. Se procesaron archivos clave como \texttt{stops.txt}, \texttt{trips.txt} y \texttt{stop\_times.txt}. En el módulo \texttt{graph\_manager.py}, iteramos sobre estos registros agrupándolos por viaje (\texttt{trip\_id}) para conectar los nodos cronológicamente, insertando aristas y previniendo la creación de multigrafos. Cuando se hallaron conexiones ya existentes entre nodos, en lugar de crear aristas redundantes, actualizamos un conjunto matemático (el atributo \texttt{routes}) adherido a la arista. 

Adicionalmente, se construyó una sub-rutina de preprocesamiento para las conexiones peatonales intra-estación. Mediante agrupaciones lógicas, se conectaron mediante aristas completas (cliques de transferencia de costo cero) a aquellas paradas que compartían identificadores de estación padre, asegurando fluidez peatonal en el grafo.

\subsection{Búsqueda y Algoritmia}
El núcleo operacional se compone de dos aproximaciones algorítmicas, encapsuladas en la función maestra de búsqueda. Ambas se basan en el Algoritmo de Dijkstra provisto por la librería \texttt{NetworkX} o en implementaciones a la medida usando estructuras de colas de prioridad (\texttt{heapq}).

\begin{enumerate}
    \item \textbf{Modo Rápido (Dijkstra Estándar):} Implementación nativa \texttt{nx.dijkstra\_path}. Utiliza netamente la función de peso $W(e)$ descrita en el modelo matemático. Su propósito es responder a la inquietud clásica: "\textit{¿Cuál es la forma más corta en distancia de llegar de A hacia B?}". Su ejecución es inmediata y no monitorea los saltos entre rutas.
    
    \item \textbf{Modo Ahorro (Dijkstra Modificado):} Es el algoritmo de mayor nivel técnico del proyecto. Modifica el estado del nodo explorado; en lugar de buscar por nodos simples, busca a través de tuplas de estado: \texttt{(nodo, buses\_tomados, rutas\_activas)}. Cuando la cola de prioridad evalúa el costo acumulado para ir hacia un vecino, inspecciona si las rutas disponibles en la nueva arista coinciden con el conjunto de rutas activas. Si el pasajero se ve forzado a cambiar de bus (transbordo real), el contador de buses se incrementa. Si dicho incremento supera un múltiplo de $3$, el algoritmo inyecta una penalidad masiva de $+10,000$ unidades. Esto obliga a la cola de prioridad a postergar y hundir en el árbol de búsqueda a las rutas que requieren gastos de dinero adicionales.
\end{enumerate}

El código se robusteció contemplando entradas donde el usuario provee grupos de nodos (por ejemplo, querer llegar a "Portal del Prado", que incluye sus módulos norte y sur). Se implementó un bucle que prueba combinaciones cartesianas de origen-destino y devuelve el óptimo global iterativo.

\subsection{Módulo de Análisis Estructural}
El archivo \texttt{graph\_analyzer.py} complementa el enrutamiento ejecutando un escaneo topológico. Utilizando las funciones integradas de la librería \texttt{NetworkX}, se calculan métricas globales (densidad, coeficiente de clustering, grado promedio) y se extraen los nodos críticos de la red basándose en su centralidad. Para evaluar la resiliencia del sistema, se implementó una rutina (\texttt{simular\_falla\_parada}) que retira un nodo del grafo en memoria y recalcula las componentes conexas, determinando de manera algorítmica si el cierre de una estación aísla por completo ciertos sectores de la ciudad.

\newpage
\section{Resultados y análisis}

Al someter el sistema a pruebas de escritorio usando los datos oficiales del GTFS de Barranquilla, observamos un comportamiento altamente favorable que demuestra la solidez de la aplicación práctica de los grafos.

\subsection{Rendimiento del Algoritmo}
A nivel computacional, el modo rápido responde casi en tiempo $O(|E| + |V| \log |V|)$ ya que la red de transporte cuenta con una densidad escasa (cada estación tiene pocos vecinos limitados por las rutas físicas de calle). 
Por su parte, el "Dijkstra de ahorro", al manejar una exploración multidimensional donde un nodo puede ser visitado en diferentes contextos (llegar al nodo en el bus X vs llegar en el bus Y), expande teóricamente el espacio de estados. Sin embargo, el almacenamiento dinámico en el diccionario de distancias \texttt{dist[estado]} frena las ramas ineficientes. Las iteraciones demostraron que los tiempos de respuesta se mantienen dentro del orden de los milisegundos, totalmente imperceptibles para un usuario final que aguarda un resultado en pantalla.

\subsection{Comparativa de Tiempos y Costos}
Las variaciones entre modos evidenciaron las dinámicas propias de Transmetro. En viajes transversales de extremo a extremo de la ciudad, el modo rápido comúnmente propone una secuencia de saltos usando alimentadores, rutas troncales y de nuevo alimentadores que geométricamente dibujan una línea recta. Si bien esto recorta la distancia de viaje en kilómetros, fácilmente supera la barrera de los 3 buses tomados, generando un cobro adicional.

Al conmutar al modo ahorro, el algoritmo conscientemente realiza un desvío geográfico. Propone al usuario caminar unos metros de más o tomar una única ruta alimentadora que realiza un recorrido perimetral más amplio, sacrificando distancia (y eventualmente unos minutos extra de viaje calculados mediante un factor constante de 22 km/h), pero preservando los transbordos bajo el umbral máximo del primer pasaje ($1$ o $2$ transbordos), salvaguardando así la economía del pasajero. Estas decisiones orgánicas reafirman la consistencia de la función objetivo definida en nuestro modelamiento matemático.

\subsection{Topología y Resiliencia de la Red}
El análisis estructural arrojó que la red de Transmetro presenta una baja densidad global, una característica típica de las redes de transporte terrestre que operan estrictamente en corredores predefinidos. Los cálculos de centralidad revelaron que ciertas estaciones actúan como nodos críticos indiscutibles (reflejado en su alto \textit{Betweenness Centrality}); estas estaciones, que usualmente fungen como portales o puntos de trasbordo troncal-alimentador, concentran el flujo de múltiples rutas. Al utilizar la función de simulación de falla sobre estas paradas críticas, observamos que el grafo tiende a fragmentarse, aumentando su número de componentes conexas. Esto demuestra algorítmicamente la vulnerabilidad del sistema de transporte masivo ante bloqueos viales, contingencias operativas o cierres por mantenimiento en sus arterias principales.

\newpage
\section{Conclusiones}

Este proyecto demostró cómo situaciones complejas y rutinarias que enfrentan los ciudadanos a diario, como la logística y el costo en el transporte público masivo, pueden ser resueltas elegantemente empleando herramientas académicas abstractas propias de las ciencias de la computación.

La modelación de la red GTFS de Transmetro mediante la Teoría de Grafos permitió transformar la geografía urbana de Barranquilla y las directrices tarifarias del operador en un problema de rutas de menor costo. Se verificó que las estructuras de grafos son idóneas para organizar datos interconectados, brindando la flexibilidad necesaria para tratar de igual manera un tramo recorrido por una máquina (viaje en bus) y un trayecto efectuado por un peatón (transferencia en plataformas).

Desde la perspectiva de diseño algorítmico, comprobamos que el algoritmo de Dijkstra tradicional, aunque poderoso, resulta limitado frente a problemas con variables heterogéneas. La modificación del espacio de estados implementada en nuestro \texttt{\_dijkstra\_ahorro} es un testimonio de la adaptabilidad de estos algoritmos clásicos, logrando codificar restricciones comerciales (3 buses por pasaje) como penalizaciones artificiales en la función heurística del algoritmo.

Finalmente, el desarrollo evidenció que las soluciones tecnológicas más útiles son aquellas centradas en el usuario. Proveer tanto métricas de eficiencia en tiempo como enfoques de mitigación de gastos genera una herramienta inclusiva y versátil. El sistema está preparado de manera resiliente, y su base en la manipulación de grafos facilita futuras escalabilidades, como la integración de estimaciones de tráfico en tiempo real mediante la modificación dinámica de los pesos de las aristas.
\end{document}
```
