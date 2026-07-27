// Handshake de versão app ↔ núcleo (UI-010). Roda após o sidecar subir.
import type { PonteNucleo } from "./ponte.js";
import { VERSAO_NUCLEO_ESPERADA } from "./versao.js";

export class ErroVersaoNucleo extends Error {
  readonly codigo = "UI-010";

  constructor(encontrada: string, esperada: string) {
    super(
      `Versão do núcleo incompatível (encontrou ${encontrada}, esperava ${esperada}). ` +
        "Reinstale o Mapas Fácil pela última release — o instalador traz app e núcleo juntos.",
    );
    this.name = "ErroVersaoNucleo";
  }
}

export async function conferirVersaoNucleo(ponte: PonteNucleo): Promise<string> {
  const resultado = (await ponte.chamar("doctor.rodar", {})) as { nucleo?: string };
  const encontrada = resultado.nucleo ?? "";
  if (encontrada !== VERSAO_NUCLEO_ESPERADA) {
    throw new ErroVersaoNucleo(encontrada || "(vazia)", VERSAO_NUCLEO_ESPERADA);
  }
  return encontrada;
}
