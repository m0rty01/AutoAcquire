// Administrative UI localization (EN/FR-CA). English source strings are the keys.
export const LANG = (typeof localStorage !== "undefined" && localStorage.getItem("aa_lang")) === "fr" ? "fr" : "en";
export const LOCALE = LANG === "fr" ? "fr-CA" : "en-CA";

export function setLang(lang) {
  localStorage.setItem("aa_lang", lang);
  window.location.reload();
}

const FR = {
  // navigation + shell
  Dashboard: "Tableau de bord", Leads: "Prospects", Pipeline: "Pipeline", Appointments: "Rendez-vous", "Test Drives": "Essais routiers",
  Communications: "Communications", Automations: "Automatisations", Inventory: "Inventaire", Partners: "Partenaires",
  Integrations: "Intégrations", Referrals: "Recommandations", Sales: "Ventes", Analytics: "Analytique", Users: "Utilisateurs",
  Settings: "Paramètres", "System Health": "État du système",
  "Database, providers, delivery, background jobs and inventory sync": "Base de données, fournisseurs, livraison, tâches de fond et synchronisation d'inventaire",
  Database: "Base de données", "Email provider (Resend)": "Fournisseur de courriel (Resend)", "SMS provider (Twilio)": "Fournisseur SMS (Twilio)",
  "Email/SMS delivery (24h)": "Livraison courriel/SMS (24 h)", "Background jobs": "Tâches de fond", "Inventory sync": "Synchronisation d'inventaire", Platform: "Plateforme", "Log out": "Déconnexion", "Copy seller link": "Copier le lien client", Back: "Retour",
  // page headers
  "Sales Pipeline": "Pipeline des ventes", "Drag leads across stages": "Glissez les prospects d'une étape à l'autre",
  "User Management": "Gestion des utilisateurs", "Create, edit and control access for your team": "Créez, modifiez et contrôlez l'accès de votre équipe",
  "Communication Center": "Centre de communication", "Every email and SMS sent to customers, dealerships and staff": "Tous les courriels et SMS envoyés aux clients, concessionnaires et employés",
  "Follow-up Automations": "Automatisations de suivi", "Triggers, delays, templates and channels — runs every 15 minutes": "Déclencheurs, délais, modèles et canaux — exécution toutes les 15 minutes",
  "Requests, confirmations, outcomes and conversion to sale": "Demandes, confirmations, résultats et conversion en vente",
  "Inventory Integrations": "Intégrations d'inventaire", "Authorized partner feeds, external ID mapping and conflict review": "Flux partenaires autorisés, correspondance des identifiants externes et revue des conflits",
  "Sales & Commission": "Ventes et commissions", "Customer profile": "Profil client", "Execution history": "Historique d'exécution",
  "Commission ledger": "Registre des commissions", "External mappings": "Correspondances externes",
  // profile tabs + cards
  Overview: "Aperçu", "Vehicle Preferences": "Préférences de véhicule", "Conversation History": "Historique des conversations",
  Activities: "Activités", "Consent & Privacy": "Consentement et confidentialité", Customer: "Client", Lead: "Prospect",
  "What they're looking for": "Ce que le client recherche", "Trade-in": "Véhicule d'échange", "AI conversation": "Conversation IA",
  "Ownership & stage": "Responsable et étape", "Follow-ups": "Suivis", "Add note": "Ajouter une note", "Send a message": "Envoyer un message",
  "Communication history": "Historique des communications", "Communication preferences": "Préférences de communication",
  "Current status": "Statut actuel", "Consent records (read-only)": "Registres de consentement (lecture seule)",
  "Communication permission history": "Historique des autorisations de communication", "Edit customer": "Modifier le client",
  "Conversation workspace": "Espace de conversation", "Activity timeline": "Chronologie des activités",
  // field labels / table heads
  Name: "Nom", Email: "Courriel", Phone: "Téléphone", "Preferred language": "Langue préférée", Location: "Emplacement",
  "Preferred contact": "Contact préféré", Created: "Créé", "Lead source": "Source du prospect", "Lead score": "Pointage",
  "Assigned dealership": "Concessionnaire assigné", "Sales representative": "Représentant", "Pipeline stage": "Étape du pipeline",
  "Last interaction": "Dernière interaction", "Next follow-up": "Prochain suivi", "Customer status": "Statut du client",
  "Vehicle type": "Type de véhicule", Make: "Marque", Model: "Modèle", "Model year": "Année", "Budget range": "Budget",
  "Max mileage": "Kilométrage max.", Transmission: "Transmission", Fuel: "Carburant", Drivetrain: "Rouage", Financing: "Financement",
  Additional: "Autres exigences", Vehicle: "Véhicule", Mileage: "Kilométrage", Condition: "État", Ownership: "Propriété",
  "Loan balance": "Solde du prêt", "Asking price": "Prix demandé", Type: "Type", "Date & time": "Date et heure", Status: "Statut",
  Dealership: "Concessionnaire", Representative: "Représentant", Requested: "Demandé", Confirmed: "Confirmé", "Notes / feedback": "Notes / commentaires",
  "Referral ID": "N° de recommandation", "Dealer group": "Groupe de concessionnaires", "Vehicle of interest": "Véhicule d'intérêt",
  Consent: "Consentement", "Delivery status": "Statut de livraison", "Sale date": "Date de vente", Verified: "Vérifié",
  "Sale amount": "Montant de vente", Commission: "Commission", Channel: "Canal", "Template / message": "Modèle / message",
  "To / from": "À / de", Sent: "Envoyé", "Agreement version": "Version de l'entente", Language: "Langue", Recipients: "Destinataires",
  "Data shared": "Données partagées", Timestamp: "Horodatage", Operational: "Opérationnel", Appointment: "Rendez-vous",
  Promotional: "Promotionnel", Source: "Source", Recorded: "Enregistré", Role: "Rôle", "Last login": "Dernière connexion",
  When: "Quand", "Dir.": "Dir.", Template: "Modèle", Recipient: "Destinataire", Rep: "Repr.", Actions: "Actions",
  Automation: "Automatisation", Kind: "Genre", "Run at": "Exécution", "Actions / error": "Actions / erreur", Total: "Total",
  Upcoming: "À venir", Completed: "Terminés", Cancelled: "Annulé", "No-shows": "Absences", "To sale": "En vente",
  "Sale $": "Vente $", Type_: "Type", Basis: "Base de calcul", "External / codes": "Externe / codes", VIN: "NIV",
  "Internal vehicle": "Véhicule interne", "Proposed change": "Changement proposé", Referrals_: "Recommandations",
  "Verified sales": "Ventes vérifiées", Conversion: "Conversion", "Commission total": "Total des commissions", Amount: "Montant",
  "Delay (minutes)": "Délai (minutes)", Channels: "Canaux", "Assign to": "Assigner à",
  // statuses (titleized)
  New: "Nouveau", Qualified: "Qualifié", "Needs Review": "À réviser", Contacted: "Contacté", Lost: "Perdu", Purchased: "Acheté",
  "New Lead": "Nouveau prospect", "Contact Required": "Contact requis", "Vehicle Matched": "Véhicule jumelé",
  "Appointment Requested": "Rendez-vous demandé", "Appointment Confirmed": "Rendez-vous confirmé", "Appointment Declined": "Rendez-vous refusé",
  "Test Drive Scheduled": "Essai routier planifié", "Test Drive Completed": "Essai routier terminé", Negotiation: "Négociation",
  "Sale Reported": "Vente déclarée", "Sale Verified": "Vente vérifiée", "Sent To Dealership": "Envoyé au concessionnaire",
  "Human Takeover": "Prise en charge humaine", "Ai Qualifying": "Qualification IA", Active: "Actif", Invited: "Invité",
  Inactive: "Désactivé", Accepted: "Accepté", Declined: "Refusé", Withdrawn: "Retiré", Granted: "Accordé", Delivered: "Livré",
  Queued: "En file", Failed: "Échec", Bounced: "Rejeté", Undelivered: "Non livré", Blocked: "Bloqué", "Not Configured": "Non configuré",
  Received: "Reçu", Reported: "Déclarée", Rejected: "Rejetée", Payable: "Payable", Paid: "Payée", Open: "Ouvert", Done: "Terminé",
  "Pending Confirmation": "En attente de confirmation", "No Show": "Absence", "Dealership Declined": "Refusé par le concessionnaire",
  Success: "Réussi", Scheduled: "Planifié", Skipped: "Ignoré", Running: "En cours", Conflict: "Conflit", Unmatched: "Non jumelé",
  Unknown: "Inconnu", None: "Aucun", Email_: "Courriel", Sms: "SMS", Outbound: "Sortant", Inbound: "Entrant",
  "Web Conversation": "Conversation Web", "Follow Up": "Suivi", "Appointment Confirmation": "Confirmation de rendez-vous",
  "Appointment Reminder": "Rappel de rendez-vous", "Test Drive Confirmation": "Confirmation d'essai routier",
  "Test Drive Reminder": "Rappel d'essai routier", "User Invitation": "Invitation utilisateur", "Password Reset": "Réinitialisation du mot de passe",
  "Lead Referred Dealer": "Avis de recommandation", "Rep Task Alert": "Alerte de tâche", "Contact Details": "Coordonnées",
  "Vehicle Preferences_": "Préférences de véhicule", "Conversation Summary": "Résumé de conversation",
  "Super Admin": "Super administrateur", "Platform Support / Operations": "Soutien / opérations", "Dealership Admin": "Administrateur concessionnaire",
  "Dealership Manager": "Directeur concessionnaire", "Sales Representative": "Représentant des ventes",
  // empty states / misc
  "No activity recorded yet.": "Aucune activité enregistrée.", "No appointments for this customer.": "Aucun rendez-vous pour ce client.",
  "No test drives for this customer yet.": "Aucun essai routier pour ce client.", "No sales reported for this customer.": "Aucune vente déclarée pour ce client.",
  "No emails or SMS sent to this customer yet.": "Aucun courriel ni SMS envoyé à ce client.", "No consent decision recorded.": "Aucune décision de consentement enregistrée.",
  "No vehicle preferences captured yet.": "Aucune préférence de véhicule saisie.", "No trade-in vehicle.": "Aucun véhicule d'échange.",
  "No inventory matches yet.": "Aucun véhicule jumelé.", "No communications yet.": "Aucune communication.", "No executions yet.": "Aucune exécution.",
  "No mappings yet.": "Aucune correspondance.", "Unassigned": "Non assigné", "None scheduled": "Aucun planifié", "Never": "Jamais",
  "Anonymous customer": "Client anonyme", Schedule: "Planifier", Add: "Ajouter", Send: "Envoyer", Edit: "Modifier",
  "Edit customer": "Modifier le client", "Save permissions": "Enregistrer les autorisations", "Record withdrawal": "Enregistrer le retrait",
  "New user": "Nouvel utilisateur", "Reset password": "Réinitialiser le mot de passe", Deactivate: "Désactiver", Reactivate: "Réactiver",
  Activate: "Activer", "New test drive": "Nouvel essai routier", "Run checks now": "Lancer les vérifications", "Save changes": "Enregistrer",
  "Sync now": "Synchroniser", "Add mapping": "Ajouter la correspondance", "Accept new": "Accepter la nouvelle", "Keep existing": "Conserver l'existante",
  Retry: "Réessayer", "Report a sale": "Déclarer une vente", "Verify": "Vérifier", "Reject": "Rejeter", Submit: "Soumettre",
  "tier adjustment": "ajustement de palier", "Imported": "Importés", "Updated": "Mis à jour", "Sold/removed": "Vendus/retirés",
  "Live vehicles": "Véhicules actifs", Conflicts: "Conflits", "Waiting on partner": "En attente du partenaire",
  "Sandbox (sample data)": "Bac à sable (données d'exemple)", "Pending Credentials": "En attente d'identifiants", Sandbox: "Bac à sable",
  "Conversation workspace": "Espace de conversation", "Hot leads": "Prospects chauds", "New leads": "Nouveaux prospects",
  "Needs review": "À réviser", "Qualification rate": "Taux de qualification", Seller: "Client", Intent: "Intention", Score: "Pointage", Appt: "RDV", "What to do…": "À faire…", "Internal note…": "Note interne…", "Search customers…": "Rechercher des clients…",
  "Search name or email…": "Rechercher nom ou courriel…", "Search customer…": "Rechercher un client…", "Loading…": "Chargement…",
};

export function tr(s) {
  if (LANG !== "fr" || s == null || typeof s !== "string") return s;
  return FR[s] ?? s;
}

export const fmtDateL = (v) => (v ? new Date(v).toLocaleString(LOCALE, { dateStyle: "medium", timeStyle: "short" }) : "—");
export const fmtDayL = (v) => (v ? new Date(v).toLocaleDateString(LOCALE) : "—");
export const moneyL = (v) => (v == null ? "—" : new Intl.NumberFormat(LOCALE, { style: "currency", currency: "CAD", maximumFractionDigits: 2 }).format(Number(v)));
