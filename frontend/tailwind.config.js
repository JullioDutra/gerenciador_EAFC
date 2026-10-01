export default { content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {
    // Paleta baseada na identidade do 5th E-Sports UniEVANGÉLICA (laranja, azul claro e amarelo sobre fundo escuro)
    colors: {
      navy: "#0A0C12",     // fundo
      panel: "#14161F",    // cartões
      panel2: "#1C1F2B",   // cartões elevados / hover
      line: "#292D3D",     // bordas sutis
      royal: "#F2621F",    // acento principal — laranja (ações, links, nav ativa)
      teal: "#38BDF8",     // acento secundário — azul claro (confirmado, classificado)
      gold: "#FFC93C",     // acento de destaque — amarelo (campeão, números, highlights)
      ice: "#F1EEE9",      // texto principal
      muted: "#9AA0AE",    // texto secundário
    },
    fontFamily: { display: ["Rajdhani", "sans-serif"], sans: ["Inter", "sans-serif"] },
    boxShadow: { soft: "0 1px 2px rgba(0,0,0,.3), 0 8px 24px -12px rgba(0,0,0,.5)" },
  } } };
