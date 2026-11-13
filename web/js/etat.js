// État partagé entre les pages (évite les imports circulaires).
export const etatApp = {
  reglages: {},
  brouillon: "",              // texte à reprendre dans une nouvelle conversation
  conversationActive: null,   // id de la conversation affichée
  fermerConversation: null,   // ferme la WebSocket quand on quitte la page
  majCompteurs: () => {},
};

export function aller(hash) { location.hash = hash; }
