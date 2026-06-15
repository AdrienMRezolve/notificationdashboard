# Demande IT — enregistrement d'une app Entra ID (interne, lecture seule)

## Version française

Objet : Enregistrement d'une app interne pour un tableau de bord de notifications (lecture seule)

Bonjour,

Je mets en place un petit tableau de bord interne qui regroupe les notifications
de mes messages (e-mail, etc.) en un seul endroit, en lecture seule — il n'envoie
jamais de message et ne fait que lire la boîte de la personne connectée, avec son
propre consentement.

Pourriez-vous enregistrer **une** application dans Microsoft Entra ID avec les
paramètres suivants :

- **Type** : compte de notre organisation uniquement (single tenant)
- **Plateforme / Redirect URI (Web)** :
  `https://rqxwdrjpkgtfooutbcgh.supabase.co/functions/v1/connect-microsoft`
- **Permission API** : Microsoft Graph → **déléguée** → `Mail.Read`
  (déléguée = l'app agit uniquement au nom de l'utilisateur connecté, sur sa
  propre boîte ; ce n'est PAS une permission applicative qui donnerait accès à
  toutes les boîtes de l'organisation)
- **Consentement administrateur** : merci de cliquer « Accorder le consentement
  administrateur » pour `Mail.Read` — comme ça chaque collègue n'a pas de
  pop-up de consentement individuel
- **Secret client** : créer un secret (« client secret ») et me le transmettre

De votre part, j'aurais besoin de :
1. **Application (client) ID**
2. **Directory (tenant) ID**
3. La **valeur du secret client** (à m'envoyer de façon sécurisée)

Précisions sécurité : permission en **lecture seule** (`Mail.Read`, pas
`Mail.ReadWrite`), **déléguée** (pas applicative), révocable à tout moment, et
aucune donnée de mail n'est stockée — seul un aperçu (objet + première ligne) et
un lien vers le message d'origine sont affichés.

Merci !

---

## English version

Subject: Register an internal Entra ID app for a read-only notifications dashboard

Hi,

I'm setting up a small internal dashboard that gathers my message notifications
(email, etc.) into one place, read-only — it never sends anything and only reads
the signed-in person's own mailbox, with their own consent.

Could you register **one** application in Microsoft Entra ID with these settings:

- **Account type**: this organization only (single tenant)
- **Platform / Redirect URI (Web)**:
  `https://rqxwdrjpkgtfooutbcgh.supabase.co/functions/v1/connect-microsoft`
- **API permission**: Microsoft Graph → **Delegated** → `Mail.Read`
  (delegated = the app acts only on behalf of the signed-in user, on their own
  mailbox — NOT an application permission that would grant org-wide mailbox access)
- **Admin consent**: please click "Grant admin consent" for `Mail.Read` so each
  colleague isn't prompted individually
- **Client secret**: create one and share it with me

What I'd need back:
1. **Application (client) ID**
2. **Directory (tenant) ID**
3. The **client secret value** (sent securely)

Security notes: **read-only** (`Mail.Read`, not `Mail.ReadWrite`), **delegated**
(not application), revocable any time, and no mail content is stored — only a
preview (subject + first line) and a link back to the original message are shown.

Thanks!

---

## Once IT replies, you set the Edge Function secrets:
```bash
supabase secrets set MS_CLIENT_ID=<application-client-id> \
                     MS_CLIENT_SECRET=<client-secret-value> \
                     MS_TENANT_ID=<directory-tenant-id>
```
(Same three values also go in the GitHub Actions secrets if you keep your own
mailbox on the env-secret path.)
