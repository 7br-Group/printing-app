FROM node:22-slim

RUN apt-get update && apt-get install -y \
    chromium \
    chromium-sandbox \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm install

COPY server.js .

EXPOSE 3000

CMD ["node", "server.js"]
