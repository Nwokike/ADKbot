# ADKBot WhatsApp Bridge

Python natively lacks robust, modern implementations for the WhatsApp Web protocol.

To bypass this and give ADKBot flawless WhatsApp integration, we built this dedicated lightweight **Node.js Bridge**.

## How it works
This bridge uses the incredible [Baileys](https://github.com/WhiskeySockets/Baileys) library to establish a direct Websocket connection. 
When `adkbot gateway` executes with WhatsApp enabled, it spins up this local Node instance seamlessly in the background to tunnel messages securely back and forth to your ADKBot brain.

*(All of the code in this directory belongs to your ADKBot installation and has been custom-styled for our ecosystem).*
