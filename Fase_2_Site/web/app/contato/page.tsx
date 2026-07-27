import type { Metadata } from "next";
import { SiteFooter } from "../../components/SiteFooter";
import { SiteHeader } from "../../components/SiteHeader";
import {
  contactEmail,
  developerName,
  linkedinUrl,
  whatsappDisplay,
  whatsappUrl,
} from "../../lib/site";

export const metadata: Metadata = {
  title: "Contato",
  description: "Entre em contato para conversar sobre o Mapas Fácil.",
};

export default function ContatoPage() {
  const repositoryUrl = process.env.NEXT_PUBLIC_REPO_URL?.trim();

  return (
    <main className="subpage contact-page">
      <div className="subpage__hero subpage__hero--contact">
        <SiteHeader />
        <div className="shell contact-hero">
          <div>
            <p className="eyebrow">Contato</p>
            <h1>
              Vamos falar sobre
              <span>mapas bem feitos.</span>
            </h1>
          </div>
          <p>
            Fale diretamente com o desenvolvedor sobre o projeto, a
            distribuição ou o fluxo de trabalho.
          </p>
        </div>
      </div>

      <section className="contact section shell">
        <div className="contact__primary">
          <span className="contact__index">01 / DESENVOLVEDOR</span>
          <h2>
            Fale com
            <span>{developerName}.</span>
          </h2>
          <p>
            Desenvolvedor do Mapas Fácil. Conte brevemente o que você quer
            produzir, melhorar ou saber sobre o sistema.
          </p>

          <div className="contact__channels">
            <a className="contact__channel" href={`mailto:${contactEmail}`}>
              <small>EMAIL</small>
              <strong>{contactEmail}</strong>
              <span aria-hidden="true">↗</span>
            </a>
            <a
              className="contact__channel"
              href={whatsappUrl}
              target="_blank"
              rel="noreferrer"
            >
              <small>WHATSAPP</small>
              <strong>{whatsappDisplay}</strong>
              <span aria-hidden="true">↗</span>
            </a>
            <a
              className="contact__channel"
              href={linkedinUrl}
              target="_blank"
              rel="noreferrer"
            >
              <small>LINKEDIN</small>
              <strong>Álvaro Emanuel</strong>
              <span aria-hidden="true">↗</span>
            </a>
          </div>
        </div>

        <aside className="contact__aside">
          <div>
            <span>RESPOSTA</span>
            <p>
              O contato é direto por e-mail, WhatsApp ou LinkedIn. Nenhuma
              mensagem é armazenada neste site.
            </p>
          </div>
          <div>
            <span>DESENVOLVIMENTO</span>
            <p>
              Interface, experiência visual e integração do site da Fase 2 por
              {` ${developerName}`}.
            </p>
          </div>
          <div>
            <span>CÓDIGO</span>
            {repositoryUrl ? (
              <a href={repositoryUrl}>Ver repositório ↗</a>
            ) : (
              <p>Repositório público ainda não informado.</p>
            )}
          </div>
        </aside>
      </section>
      <SiteFooter />
    </main>
  );
}
