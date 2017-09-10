FROM python:3.6-stretch

ENV PULSE_SERVER /run/pulse/native

COPY misc/docker-pulseaudio-entrypoint.sh /docker-entrypoint.sh

COPY requirements.txt /opt/requirements.txt
COPY test_requirements.txt /opt/test_requirements.txt

RUN apt-get update && \
    apt-get install -y --no-install-recommends git gcc python3 libpython3.5 libatlas3-base libportaudio2 swig pulseaudio-utils pulseaudio libopus0 libspeex1 libspeexdsp1 make g++ python3-dev musl-dev portaudio19-dev swig libatlas-base-dev libopus-dev libsamplerate0-dev libspeex-dev libspeexdsp-dev && \
    apt-get clean && \
    pip install numpy && \
    pip install -r /opt/requirements.txt && \
    apt-get -y purge python3-dev musl-dev portaudio19-dev libatlas-base-dev g++ make libopus-dev libspeex-dev libspeexdsp-dev && apt -y autoremove --purge && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
# Configure pulseaudio
RUN echo enable-shm=no >> /etc/pulse/client.conf


RUN mkdir /workdir

WORKDIR /opt
COPY setup.py /opt/setup.py
COPY tuxeatpi_speech_nuance /opt/tuxeatpi_speech_nuance
RUN python setup.py install

WORKDIR /workdir

COPY dialogs /dialogs
COPY intents /intents

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["tep"]
