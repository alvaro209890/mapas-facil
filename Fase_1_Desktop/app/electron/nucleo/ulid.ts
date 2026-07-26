// ULID em string é a convenção de `id` do repositório (AGENT_BRIEF §Convenções).
// Implementação local: 26 caracteres, Crockford base32, monotônico dentro do
// mesmo milissegundo. Uma dependência a menos no processo main.
const ALFABETO = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

let ultimoTempo = -1;
let ultimoAleatorio: number[] = [];

function codificarTempo(tempo: number, tamanho: number): string {
  let saida = "";
  for (let i = tamanho - 1; i >= 0; i -= 1) {
    saida = ALFABETO[tempo % 32] + saida;
    tempo = Math.floor(tempo / 32);
  }
  return saida;
}

function aleatorios(tamanho: number): number[] {
  return Array.from({ length: tamanho }, () => Math.floor(Math.random() * 32));
}

function incrementar(valores: number[]): number[] {
  const copia = [...valores];
  for (let i = copia.length - 1; i >= 0; i -= 1) {
    if (copia[i] < 31) {
      copia[i] += 1;
      return copia;
    }
    copia[i] = 0;
  }
  return aleatorios(copia.length);
}

export function novoUlid(agora: number = Date.now()): string {
  if (agora === ultimoTempo) {
    ultimoAleatorio = incrementar(ultimoAleatorio);
  } else {
    ultimoTempo = agora;
    ultimoAleatorio = aleatorios(16);
  }
  return codificarTempo(agora, 10) + ultimoAleatorio.map((n) => ALFABETO[n]).join("");
}
