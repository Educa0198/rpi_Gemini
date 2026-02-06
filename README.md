# RPI

Este repositório reúne e documenta as diversas **aplicações do Raspberry Pi (RPI)** no contexto da coleta automatizada de dados no transporte público, com foco em soluções de **baixo custo, robustez e escalabilidade**.

# Aplicações 

- **Coletar endereços MAC utilizando o RPI**  
  O RPI identifica dispositivos próximos, registrando a presença dos passageiros ao longo do trajeto.
- **Associar dados MAC à localização GPS via dispositivo Android**  
  O sistema envia os MACs via Bluetooth para um dispositivo Android, onde um aplicativo obtém a localização GPS e associa as informações.
- **Armazenar os dados localmente para posterior análise**  
  As informações são salvas no celular para tratamento posterior, possibilitando estudos detalhados de fluxo de passageiros.
  
# Objetivos 

O sistema desenvolvido tem como foco aprimorar pesquisas de "sobe e desce" de passageiros no transporte coletivo, utilizando uma solução embarcada, o RPI, com o objetivo principal de criar um sistema autônomo e confiável para pesquisa de origem e destino, por meio da coleta de dados de presença de passageiros via endereços MAC, permitindo a identificação precisa dos pontos de embarque e desembarque.

# Desafios

Durante a Prova de Conceito (POC) inicial, diversos desafios técnicos foram identificados no uso do Raspberry Pi como núcleo do sistema. Identificar esses desafios é fundamental para determinar as melhorias necessárias: 

- **Setup manual após desligamento**  
  O RPI precisa ser reconfigurado manualmente a cada reinicialização, dificultando o uso contínuo em campo e exigindo intervenção técnica constante.
- **Falta de feedback visual no dispositivo**  
  Não há uma indicação clara no hardware sobre o estado de funcionamento do sistema (se está operando corretamente, coletando dados ou enfrentando falhas).
- **Instabilidade na conexão Bluetooth com o Android**  
  Problemas frequentes no pareamento e manutenção da conexão entre o RPI e o dispositivo Android comprometem a transmissão dos dados coletados.
- **Registros de MACs inconsistentes**  
  O RPI ocasionalmente coleta endereços MAC com formatação incompleta ou inválida, dificultando a análise posterior.
- **Ausência de logs no sistema do RPI**  
  A falta de registros de log dificulta a identificação e diagnóstico de falhas durante a operação, limitando a capacidade de correção e manutenção remota.
- **Instabilidade da Conexão Bluetooth:**
  Problemas no pareamento e na manutenção da conexão entre RPi e Android.


  



