FROM apify/actor-node-puppeteer-chrome:20

COPY package*.json ./
RUN npm install --include=dev --audit=false

COPY . ./

CMD npm start --silent