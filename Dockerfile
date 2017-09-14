FROM tuxeatpi/pulseaudio

COPY dialogs /dialogs
COPY intents /intents

COPY test_requirements.txt /opt/test_requirements.txt
COPY requirements.txt /opt/requirements.txt

RUN sed -i 's/.*python-aio-etcd.*//' /opt/requirements.txt && \
    sed -i 's/.*tuxeatpi-common.*//' /opt/requirements.txt && \
    apt-get update && \
    apt-get install -y --no-install-recommends libatlas3-base libportaudio2 swig libopus0 libspeex1 libspeexdsp1 g++ python3-dev musl-dev portaudio19-dev libatlas-base-dev libopus-dev libsamplerate0-dev libspeex-dev libspeexdsp-dev && \
    apt-get clean && \
    pip install numpy && \
    pip install -r /opt/requirements.txt && \
    apt-get -y purge g++ python3-dev musl-dev portaudio19-dev libatlas-base-dev libopus-dev libsamplerate0-dev libspeex-dev libspeexdsp-dev && apt -y autoremove --purge && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY setup.py /opt/setup.py
COPY tuxeatpi_nlu_nuance /opt/tuxeatpi_nlu_nuance
RUN cd /opt && python setup.py install

WORKDIR /workdir
CMD ["nlu-nuance"]
