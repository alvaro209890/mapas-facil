import type { Metadata } from "next";
import Link from "next/link";
import { SiteFooter } from "../../components/SiteFooter";
import { SiteHeader } from "../../components/SiteHeader";

export const metadata: Metadata = {
  title: "Requisitos",
  description:
    "O que você precisa para usar o Mapas Fácil no Windows, com ou sem ArcMap.",
};

const requisitos = [
  {
    number: "01",
    title: "Windows 10 ou 11",
    text: "O Mapas Fácil é um aplicativo desktop. A primeira distribuição é voltada ao ambiente Windows.",
  },
  {
    number: "02",
    title: "Conta criada no aplicativo",
    text: "O cadastro usa e-mail e senha local. Não existe conta, login ou envio de senha neste site.",
  },
  {
    number: "03",
    title: "ArcMap é opcional",
    text: "Com ArcMap, o app produz o fluxo MXD via ArcPy. Sem ArcMap, mantém o patch compatível e a saída PDF nativa.",
  },
  {
    number: "04",
    title: "Sua própria chave DeepSeek",
    text: "A chave é guardada pelo Credential Manager do Windows e usada somente pelo aplicativo. Ela nunca é informada neste site.",
  },
];

export default function RequisitosPage() {
  return (
    <main className="subpage">
      <div className="subpage__hero">
        <SiteHeader />
        <div className="shell subpage__hero-content">
          <p className="eyebrow">Antes de instalar</p>
          <h1>
            Um ambiente simples.
            <span>Seu fluxo preservado.</span>
          </h1>
          <p>
            Veja o que o computador precisa e como cada parte do Mapas Fácil
            funciona no seu ambiente.
          </p>
        </div>
      </div>

      <section className="requirements section shell">
        <div className="requirements__intro">
          <span>REQUISITOS / 04</span>
          <p>
            O site apenas apresenta e distribui o instalador. Seus projetos,
            sua conta e suas credenciais ficam no aplicativo.
          </p>
        </div>
        <div className="requirements__list">
          {requisitos.map((item) => (
            <article className="requirement" key={item.number}>
              <span>{item.number}</span>
              <h2>{item.title}</h2>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="inline-cta">
        <div className="shell inline-cta__inner">
          <div>
            <p className="eyebrow">Tudo certo por aí?</p>
            <h2>Confira a disponibilidade do instalador.</h2>
          </div>
          <Link className="button button--light" href="/download">
            Ir para download <span aria-hidden="true">↗</span>
          </Link>
        </div>
      </section>
      <SiteFooter />
    </main>
  );
}
