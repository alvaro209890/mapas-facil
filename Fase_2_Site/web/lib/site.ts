export const developerName =
  process.env.NEXT_PUBLIC_DEVELOPER_NAME?.trim() || "Álvaro Emanuel";

export const contactEmail =
  process.env.NEXT_PUBLIC_CONTACT_EMAIL?.trim() ||
  "alvaroemanuel642@gmail.com";

export const whatsappNumber =
  process.env.NEXT_PUBLIC_WHATSAPP_NUMBER?.replace(/\D/g, "") ||
  "5566984396232";

export const whatsappDisplay = "+55 (66) 98439-6232";
export const whatsappUrl = `https://wa.me/${whatsappNumber}`;

export const linkedinUrl =
  process.env.NEXT_PUBLIC_LINKEDIN_URL?.trim() ||
  "https://www.linkedin.com/in/alvaro-emanuel-4673a63a7/";
