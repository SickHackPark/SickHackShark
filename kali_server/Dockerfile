FROM kalilinux/kali-rolling:latest
ENV DEBIAN_FRONTEND=noninteractive
RUN echo 'deb http://mirrors.ustc.edu.cn/kali kali-rolling main non-free non-free-firmware contrib' \
         > /etc/apt/sources.list && \
    echo 'deb-src http://mirrors.ustc.edu.cn/kali kali-rolling main non-free non-free-firmware contrib' \
         >> /etc/apt/sources.list
ADD https://archive.kali.org/archive-keyring.gpg /tmp/archive-keyring.gpg
RUN mv /tmp/archive-keyring.gpg /usr/share/keyrings/kali-archive-keyring.gpg && \
    chmod 644 /usr/share/keyrings/kali-archive-keyring.gpg

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        kali-linux-large