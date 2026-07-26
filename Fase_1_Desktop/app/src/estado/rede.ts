// Estado de rede do renderer (F1-02 §Estados — "Sem internet").
//
// Só o browser/Electron sabe se há rede (`navigator.onLine` + eventos
// `online`/`offline`). Nada aqui chama o núcleo: o banner é informativo —
// workspace, chats e galeria continuam locais; camadas externas (A13) usam
// cache com idade quando a rede cai.

import { useEffect, useState } from "react";

function lerOnline(): boolean {
  if (typeof navigator === "undefined") return true;
  return navigator.onLine;
}

/** `true` quando o SO reporta conectividade. Sem evento, não inventa offline. */
export function useOnline(): boolean {
  const [online, setOnline] = useState(lerOnline);

  useEffect(() => {
    const marcarOnline = () => setOnline(true);
    const marcarOffline = () => setOnline(false);
    window.addEventListener("online", marcarOnline);
    window.addEventListener("offline", marcarOffline);
    // Re-lê na montagem — o valor inicial pode ter sido do SSR/jsdom.
    setOnline(lerOnline());
    return () => {
      window.removeEventListener("online", marcarOnline);
      window.removeEventListener("offline", marcarOffline);
    };
  }, []);

  return online;
}
