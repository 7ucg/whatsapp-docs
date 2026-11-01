<!-- src-sha1: c9f42e3645bee848584358bb7a4660a293218e2e -->
# WhatsApp Eventos — Full RE Report
**Versão:** 2.26.41.6 | **Data:** 2026-11-01
**Escopo:** Eventos no estilo calendário (`eventMessage`, `eventInviteMessage`, `eventCoverImage`), RSVP criptografado (`encEventResponseMessage` / `EventResponseMessage`), subsistema de app "Events v2" (`com.whatsapp.eventsv2.*`: DB local, sincronização GraphQL, notificações push MEX, pipeline de imagem de capa, link de convite/QR), ciclo de vida (criar/editar/cancelar/excluir/sair), estados de RSVP, regras de visibilidade de convidado/localização, contexto grupo vs. 1:1 vs. comunidade, restrição de dispositivo companion, catálogo de operações GraphQL, lembretes

---

## 1. O que é

Um "Event" (evento) é um objeto no estilo calendário (nome, descrição, janela de tempo, localização, link opcional de chamada de vídeo/voz) que pode ser postado em um chat 1:1, em um grupo, ou compartilhado via link/QR independente, com convidados podendo fazer RSVP (Going / Maybe / Not going). O recurso é entregue por duas superfícies de wire ao mesmo tempo: uma mensagem de chat comum criptografada E2E (`Message.eventMessage` / `Message.eventInviteMessage`) que renderiza o cartão de convite na transcrição, e um plano de controle paralelo GraphQL + push MEX (`com.whatsapp.eventsv2.*`, pacote novo na 2.26.41.6) que mantém um banco de dados local de eventos sincronizado independentemente do histórico do chat. A criptografia do RSVP (caso de uso HKDF "Event Response", AES-GCM) é compartilhada com reações/enquetes/comentários e está documentada em `WA_MESSAGE_SECRETS.md`; este relatório cobre apenas a camada de modelo de evento e ciclo de vida.

| Entidade | Campo em `Message` | Tipo (obf.) | Papel |
|--------|-----------------|-------------|------|
| `eventMessage` | **75** | `EventMessage` | evento de calendário base, postado em um chat |
| `encEventResponseMessage` | **76** | `EncEventResponseMessage` (`DRN`) | mensagem de acompanhamento de RSVP criptografada |
| `eventCoverImage` | **85** | `FutureProofMessage` | wrapper genérico, carrega a foto de capa como um `imageMessage` aninhado |
| `eventInviteMessage` | **122** | `EventInviteMessage` (`DTQ`) | cartão de convite "Events v2", superconjunto de `eventMessage` |
| `eventResponses` (repetido) | **61**, no equivalente de `WebMessageInfo` (`C30626DTu`) | `EventResponse` | resumo de RSVP por convidado, transportado na sincronização de histórico |
| `eventAdditionalMetadata` | **64**, mesmo host | `EventAdditionalMetadata` | único bool `isStale` |

Todos os campos de proto e os campos de texto puro do RSVP abaixo foram relidos diretamente das classes da 2.26.41.6 (`DRP`, `DRN`, `DU9`, `E2D`, `C9T8` — **found**) e verificados contra o container de nível superior `Message` em `Tools/proto-extractor/research/2.26.41.6/whatsapp-deobfuscated.proto`. Níveis: **found** = lido no código/strings, **inferred** = deduzido, **unknown** = não resolvido.

---

## 2. `EventMessage` (campo 75) — evento base

Inalterado desde o catálogo da era 2.26.35.2; ainda 12 campos na 2.26.41.6.

| Campo | # | Tipo | Notas |
|-------|---|------|-------|
| `contextInfo` | 1 | `ContextInfo` | carrier padrão de citação/menções |
| `isCanceled` | 2 | bool | definido pela ação de cancelamento |
| `name` | 3 | string | título do evento |
| `description` | 4 | string | |
| `location` | 5 | `Message.LocationMessage` | pin de localização estático (lat/long/nome/endereço), *não* ao vivo |
| `joinLink` | 6 | string | URL de entrada genérica (campo legado; substituído pelo link de convite do Events v2 para novos eventos) |
| `startTime` | 7 | int64 | segundos unix |
| `endTime` | 8 | int64 | segundos unix |
| `extraGuestsAllowed` | 9 | bool | alternância de "+1" |
| `isScheduleCall` | 10 | bool | mesmo modelo usado para o ponto de entrada "Schedule a call" |
| `hasReminder` | 11 | bool | |
| `reminderOffsetSec` | 12 | int64 | segundos antes de `startTime` |

`reminderOffsetSec` é preenchido a partir de um picker fixo (`EventReminderBottomSheet`, strings **found**): "Never", "Time of event", "15 minutes before", "30 minutes before", "1 hour before", "1 day before". O mapeamento de segundos 0/900/1800/3600/86400 é **inferred** (não lido como literais; a tabela de opção-para-segundos do picker vive em uma classe — `BXa`/`C27637BzN` — cujo pool de constantes o jadx não resolveu).

---

## 3. `EventInviteMessage` (campo 122, obf. `DTQ`) — convite "Events v2"

Cresceu de 9 para 13 campos ao longo das releases; a 2.26.41.6 traz todos os 13. **Correção ao material de partida**: o `Messages/eventInviteMessage/info.md` commitado (capturado na 2.26.35.2) para no campo 9 (`callLink`) e está sem os campos 10–13, confirmados presentes nesta build pela leitura direta de `DTQ`:

| Campo | # | Tipo | Adicionado | Notas |
|-------|---|------|-------|-------|
| `contextInfo` | 1 | `ContextInfo` | base | |
| `eventId` | 2 | string | base | id de evento atribuído pelo servidor |
| `eventTitle` | 3 | string | base | |
| `jpegThumbnail` | 4 | bytes | base | miniatura de capa embutida |
| `startTime` | 5 | int64 | base | |
| `caption` | 6 | string | base | |
| `isCanceled` | 7 | bool | base | |
| `endTime` | 8 | int64 | base | |
| `callLink` | 9 | string | base | estilo `https://call.whatsapp.com/video/...` |
| `coverImageHandle` | 10 | string | 2.26.38.10 | referência de media-handle, alternativa ao `jpegThumbnail` embutido |
| `locationName` | 11 | string | 2.26.38.10 | rótulo de localização legível por humanos |
| `lastUpdatedTsUsec` | 12 | int64 | 2.26.38.10 | microssegundos; avança em cada `UpdateEvent` |
| `status` | 13 | int32 (open enum) | **2.26.41.6** | status de nível de evento; classe enum não recuperável estaticamente |

`status` (13) é o único campo novo no wire nesta release. Os nomes dos membros do seu enum são **unknown** no nível de proto — o jadx não conseguiu recuperar a classe por trás deste int32 de open-enum. No entanto, o vocabulário de status voltado ao GraphQL usado pelas variáveis relacionadas `rsvp_status`/`UpdateEvent.status` foi recuperado de forma independente (§6) e é um candidato plausível, mas não confirmado, para a mesma semântica; não está comprovado que os dois compartilhem a mesma representação no wire.

---

## 4. `eventCoverImage` (campo 85) — wrapper de foto de capa

`FutureProofMessage { optional Message message = 1; }` — o mesmo wrapper genérico usado para `lottieStickerMessage`, `statusMentionMessage`, etc. Sem campos específicos de evento; o `message` aninhado carrega um `imageMessage` comum. O código consumidor (`EventCoverImageLoader`, `EventCoverImageThumbnailCreator`, `EventCoverImageUrlResolver`) trata isso como um anexo de imagem normal — nenhuma validação adicional além do unwrapping genérico do wrapper foi encontrada.

O Events v2 também suporta imagens de capa **preset** (`EventPresetCoverImagesRepository`, catálogo buscado via GraphQL, variáveis `cover_image_blob`/`is_preset_image` em `CreateEvent`/`UpdateEvent`) como alternativa a uma foto enviada pelo usuário.

---

## 5. RSVP: `encEventResponseMessage` e `EventResponseMessage`

### 5.1 Formato no wire (found, `DRN`/`DRP`/`E2D` lidos diretamente)

| Carrier | Campo | # | Tipo |
|---------|-------|---|------|
| `EncEventResponseMessage` (`DRN`, campo 76) | `eventCreationMessageKey` | 1 | `MessageKey` (`BD5`) |
| | `encPayload` | 2 | bytes |
| | `encIv` | 3 | bytes |
| `EventResponseMessage` (`DRP`, o texto puro AES-GCM) | `response` | 1 | enum `E2D` |
| | `timestampMs` | 2 | int64 |
| | `extraGuestCount` | 3 | int32 |

Valores de `E2D` (found, `E2D.java`): **0 UNKNOWN, 1 GOING, 2 NOT_GOING, 3 MAYBE**.

Isso confirma diretamente `WA_MESSAGE_SECRETS.md` §"encEventResponseMessage **76**" e resolve um conflito no dump de proto auto-extraído (`Etc/whats-new-2.26.41.6/deep/social-and-messaging.md`, que — devido a um bug de recuperação de nome de campo observado no próprio texto, "missing name slot at field #3" — lista `EventResponseMessage` como `timestampMs=1, extraGuestCount=2, field3=3`). A leitura direta da classe (a string de ordem de campos `BUILD_MESSAGE_INFO` de `DRP` e as constantes `RESPONSE_FIELD_NUMBER=1`/`TIMESTAMP_MS_FIELD_NUMBER=2`/`EXTRA_GUEST_COUNT_FIELD_NUMBER=3`) resolve a questão: **`response` é o campo 1, não o campo 3.**

### 5.2 Caminho de envio (found, `DU9.ADr`)

`DU9` (handler de caso de uso de resposta a evento, estende `F2P`) constrói um `DRP` a partir de um enum de nível de app `C9T8` (`UNKNOWN=0, GOING=1, NOT_GOING=2, MAYBE=3` — numericamente idêntico a `E2D`, confirmando ser um espelho 1:1 direto via conversor `EW0.A01`) mais um timestamp e um int `extraGuestCount`, criptografa isso com o caso de uso HKDF `"Event Response"` via `MessageSecretCryptoHelper` (`C33285Eeb.A03`), e envolve o texto cifrado/IV/chave da mensagem original em um `DRN`. `AAl()` grava o `<meta event_type="response">` da stanza de saída. O detalhe de criptografia (derivação HKDF, AES-GCM, AAD = `targetId‖0x00‖modifier`, retry de remetente/LID) **não é repetido aqui** — ver `WA_MESSAGE_SECRETS.md` §2–9, 16.

### 5.3 Mais três enums no formato de RSVP (found) — uma pegadinha

Além do enum de wire `E2D` e de seu espelho `C9T8`, o app define pelo menos três *outras* enumerações de status de RSVP com **ordenações de membros diferentes**, cada uma usada em uma camada diferente:

| Enum (obf.) | Membros (ordinal) | Usado para |
|---|---|---|
| `E2D` | 0 UNKNOWN, 1 GOING, 2 NOT_GOING, 3 MAYBE | texto puro de wire `EventResponseMessage.response` |
| `C9T8` | 0 UNKNOWN, 1 GOING, 2 NOT_GOING, 3 MAYBE | espelho de nível de app de `E2D`, passado para `DU9.ADr` |
| `C9T6` | 0 GOING, 1 NOT_GOING, 2 MAYBE, 3 NO_RESPONSE | ordenação local `dbValue` (`EventRsvpBottomSheet`, DB local), **sem slot UNKNOWN**, tem `NO_RESPONSE` em seu lugar |
| `C9U0` | strings `serverValue`: `UNSET_OR_UNRECOGNIZED_ENUM_VALUE`, `GOING`, `MAYBE`, `NOT_GOING`, `NO_RESPONSE` | variável GraphQL `rsvp_status` (`UpdateEventRsvp`, `JoinEventViaLink`) |

Isso resolve parte da lacuna "RSVP enum unknown" anotada para a superfície GraphQL em `Etc/whats-new-2.26.41.6/deep/social-and-messaging.md`: a variável **GraphQL** `rsvp_status` aceita as strings literais `GOING` / `MAYBE` / `NOT_GOING` / `NO_RESPONSE` (found, `C9U0.serverValue`, consumidor `C207188s3.B2x()` lendo a chave `"rsvp_status"`). A classe enum do wire-proto `EventInviteMessage.status` (campo 13, §3) continua não recuperada e **não está comprovado** que compartilhe este vocabulário.

Um quinto conjunto separado de valores inteiros de "rótulo de status" (found, `C2115191e.A00`, usado para o chip de encaminhamento/preview no chat) mapeia `1 GOING, 2 GOING_WITH_GUEST, 3 NOT_GOING, 4 MAYBE, 5 NOT_RESPONDED, 6 CANCELED, default CREATOR` — um conjunto de rótulos de debug/exibição de UI, não um valor de wire.

---

## 6. Superfície GraphQL do Events v2 (schema `www`, doc_ids found)

Existem 16 operações persistidas no `whatsapp-android-www_client_persist_ids.json` distribuído; variáveis recuperadas a partir dos call sites do APK (documentadas em `Querys/www/guides/events.md`, que este relatório verificou cruzadamente em vez de re-derivar).

| Operação | doc_id | Operação | doc_id |
|----|--------|----|--------|
| `CreateEvent` | `27122934507384369` | `UpdateEvent` | `27442441785378771` |
| `DeleteEvent` | `24671535952543811` | `UpdateEventRsvp` | `27592470423757790` |
| `GetEvent` | `27529572846713636` | `ListEvents` | `27633532006268526` |
| `GetEventCoverImage` | `28048111841543330` | `AddEventInvitations` | `28162575909992756` |
| `GetEventLinkPreview` | `27639296169058396` | `RemoveEventInvitations` | `27696932319970038` |
| `GetOrCreateEventInviteLink` | `26392982740362906` | `RemoveSelfEventInvitation` | `27063717026648637` |
| `JoinEventViaLink` | `27669318929396727` | `RotateEventInviteLink` | `27134834146102810` |
| `ValidateCachedEventIDs` | `27508030125525954` | mex `LogEventInviteCreate` | `27409709725288255` |

Principais variáveis recuperadas (found): `CreateEvent`/`UpdateEvent` recebem `chat_jid`, `description`, `max_additional_guests`, `is_group_based_event`, `is_shareable`, `cover_image_handle`/`cover_image_blob`/`is_preset_image`, `location_address`/`location_web_url`, `call_link_media_type`, `call_link_waiting_room_enabled`; `UpdateEvent` adicionalmente recebe `clear_location`, `clear_location_coordinates`, `hide_invitee_list`, `link_id`, `status`. `UpdateEventRsvp`/`JoinEventViaLink` recebem `event_id`/`link_token`, `rsvp_status`, `extra_guest_count`. O transporte é `inferred` (POST de `doc_id` persistido, mesmo padrão dos outros ops `www`); nenhum tráfego foi capturado.

### 6.1 Notificações push MEX (found, distinto do pull GraphQL acima)

`DefaultEventsNotificationRepository` faz o parse de dois schemas de payload push **MEX** — `xwa2_notify_event_on_invite` e `xwa2_notify_event_on_update` (nomes literais de nó em exceções lançadas, found) — carregando `start_ts_sec`, `cover_image.handle`/`cover_image.uri`, localização e campos de link de chamada, e faz upsert deles diretamente no DB local de eventos (`DefaultLocalEventsDataSource.upsertEvents`). Isso significa que um evento pode aparecer na lista local de Events de um dispositivo **sem** que o dispositivo jamais tenha recebido o plano de mensagem de chat (`eventMessage`/`eventInviteMessage`) referente a ele — o servidor envia ativamente notificações de convite/atualização via MEX de forma independente da entrega pelo chat. No primeiro convite, o status local de RSVP assume por padrão `NO_RESPONSE` (`C9T6.A05.dbValue`).

---

## 7. Armazenamento local e bridge legado

`EventsDatabaseDataSource` (DB local no estilo Room) é o armazenamento canônico do Events v2; `GraphqlEventsDataSource` o preenche a partir das ops do §6; `FMessageEventsDataSource` faz a ponte do modelo **mais antigo**, baseado só em mensagem de chat (`eventMessage`/`eventInviteMessage` como linhas `FMessage` simples, classe `C213509Ao` — também a classe que controla a geração de `messageSecret` para mensagens de evento conforme `WA_MESSAGE_SECRETS.md` §"prepare send"), para o mesmo stream `observeEventPreviews()` consumido pela UI. Na prática: um evento criado por um cliente mais antigo (ou antes de o Events v2 existir) ainda é renderizado a partir da mensagem de chat; um evento criado pelo Events v2 é respaldado por DB e sincronizado via GraphQL, com a mensagem de chat funcionando como o cartão de convite compartilhável.

---

## 8. Ações do ciclo de vida

| Ação | Quem | Mecanismo | Efeito |
|--------|-----|-----------|--------|
| **Criar** | qualquer membro do chat (grupo) / qualquer uma das partes (1:1) / qualquer pessoa em um contexto elegível para QR | `CreateEvent` (GraphQL), depois `eventInviteMessage` postada no chat | o servidor atribui o `eventId`; `EventComposerFragment` coleta nome/descrição/horário/localização/capa/lembrete/alternância de convidados/tipo de mídia do link de chamada |
| **Atualizar** | anfitrião | `UpdateEvent` (GraphQL); `lastUpdatedTsUsec` (campo 12) avança | texto de notificação direcionado dependendo de quais campos mudaram: "Event date has been updated.", "...date and location...", "...date and time...", "...date, time and location...", "...location has been updated.", "...time has been updated.", "...time and location..." (todas found, strings distintas por diff) |
| **Cancelar** | anfitrião | define `isCanceled`/`status`; diálogo de confirmação "Cancel event" / "Are you sure you want to cancel this event?" | "Event canceled"; texto de push "%1$s canceled %2$s"; "Guests can no longer respond to the event." / "You can no longer respond to the event." — RSVP se encerra |
| **Excluir** | anfitrião | `DeleteEvent` (GraphQL) | removido da lista local de eventos do anfitrião; a(s) mensagem(ns) de convite no chat permanece(m) visível(is); "People on the guest list will see the event has been deleted." |
| **Sair** | convidado | ação local, sem implicar mudança de RSVP | o convidado para de receber futuras atualizações do evento: "You can only see event changes made before you left." |
| **Remover convidado** | anfitrião | remove o convidado; **reseta o link de convite** (`RotateEventInviteLink`) | "Guest removed and event link reset" — medida explícita anti-reentrada para que a cópia do link do convidado removido deixe de funcionar; remover um convidado que entrou via link **não** invalida retroativamente outros que já usaram aquele link |
| **Denunciar evento** | convidado | envia relatório ao WhatsApp | "No one in the event will know about this report."; também pode disparar a saída do evento |
| **Suspender** (moderação) | lado do servidor (enforcement de política) | distinto de cancelamento | "Event suspended", "can't be changed right now"; um estado bloqueado do qual o anfitrião não pode editar para saída |

Remover convidados individualmente (`RemoveEventInvitations`) é diferente de remover um convidado que já entrou (`RemoveEventGuestUseCase`); `AddEventInvitations`/`RemoveSelfEventInvitation` completam o gerenciamento da lista de convites.

---

## 9. UI de RSVP e estados

`EventRsvpBottomSheet` oferece quatro opções de rádio vinculadas aos resource ids `rsvp_going_btn`, `rsvp_going_with_guest_btn` (mostrado apenas quando `extraGuestsAllowed` está definido e o viewer escolhe uma contagem de convidados > 0), `rsvp_not_going_btn`, `rsvp_maybe_btn`; nenhum botão fica marcado para o estado não respondido/`NO_RESPONSE`. Rótulos (found, strings.xml): "Going", "Going with guest", "Maybe", "Not going". Um convidado pode adicionalmente trazer uma contagem de acompanhante (`extraGuestCount`, campo de wire 3 de `EventResponseMessage`), controlada por `EventMessage.extraGuestsAllowed` (campo 9) / `"You can't turn off 'Allow guests' for this event."` uma vez que convidados já tenham feito RSVP com acompanhante.

RSVP de não usuário do WhatsApp é explicitamente suportado através do link de entrada: `"Guests can respond even if they're not on WhatsApp."` — `JoinEventViaLink` recebe `rsvp_status` diretamente sem uma sessão WA autenticada, ou seja, o caminho criptografado `encEventResponseMessage` não é o único canal de RSVP; RSVPs baseados em link passam, em vez disso, por GraphQL em texto puro.

---

## 10. Modelo de visibilidade e privacidade

Este é o fato mais importante de "não confundir" sobre Events: diferente do conteúdo comum de chat, **os metadados do evento são explicitamente divulgados ao servidor**, não puramente opacos para E2E.

| String (found) | Resource | Significado |
|---|---|---|
| "Event details will be visible to guests and WhatsApp." | `str19d9` | nome/descrição/horário/localização são legíveis no lado do servidor (consistente com eles serem variáveis GraphQL de `CreateEvent`/`UpdateEvent`, não apenas bytes de proto criptografados) |
| "Event details are visible to guests and WhatsApp. Your personal messages and calls remain end-to-end encrypted." | `str1a3f` | escopo explícito: a garantia E2EE *não* se estende aos detalhes do evento |
| "Your name and response will be visible to other guests and WhatsApp." | `str1a08` | identidade do RSVP + resposta também é visível ao servidor (consistente com `UpdateEventRsvp` ser uma mutation GraphQL em texto puro, separada do eco criptografado `encEventResponseMessage` no plano do chat) |
| "Respond to see the event location and more." / "Respond to see location" | `str19c7`/`str19c4` | a localização fica **bloqueada atrás do RSVP** para convidados que ainda não responderam |
| "You can only see guests in your contacts or who you've messaged on WhatsApp." | `str1974` | a visibilidade da lista de convidados é limitada ao próprio grafo de contatos/chat do viewer, não uma lista completa |
| "Anyone with the link can see the event and share it with others, even if they're not on WhatsApp." | `str198b` | o link de convite/QR contorna totalmente a membership — posse do link é o controle de acesso |

Então: a criptografia E2E de `encEventResponseMessage` (HKDF + AES-GCM, §5, `WA_MESSAGE_SECRETS.md`) protege o payload do RSVP **na transcrição do chat / contra o relay**, mas a mesma resposta de RSVP e os próprios metadados do evento são enviados independentemente ao servidor em texto puro pelo plano de controle GraphQL para sincronização, descoberta e convidados baseados em link (não-WA). Os dois planos não são mutuamente exclusivos — eles coexistem para o mesmo evento.

---

## 11. Contexto grupo vs. 1:1 vs. comunidade

- **Chat 1:1**: qualquer uma das partes pode criar um evento; a variável GraphQL `is_group_based_event` é false.
- **Chat em grupo**: `is_group_based_event: true`; o composer mostra "Created for:" com o grupo identificado; convites também podem ter origem na membership do grupo (`EventInviteFromGroupsLoadController`, `EventInviteGroupFetcher`), permitindo que um anfitrião convide pessoas de outros grupos compartilhados.
- **Comunidade**: Events também aparecem no nível de comunidade — "Events in announcements", "Community events", "See all community events" (strings found) — uma lista de eventos de toda a comunidade, distinta dos eventos de um único grupo.
- **Independente / baseado em link**: um evento não precisa estar vinculado a nenhum chat; `GetOrCreateEventInviteLink` + `EventInviteLinkQrActivity` produzem um link/QR compartilhável independente de membership de chat (§10, `str198b`).

A classificação de suporte a companion de `eventMessage` (`WA_MESSAGE_SECRETS.md` §15, `CompanionSupportVerifier`) permite a stanza `type="event"` em um dispositivo vinculado (companion) — ou seja, a bolha de convite ainda pode ser *recebida e armazenada* lá — mas a interação com ela é bloqueada: `EventsCompanionRedirectDialog` + a string `"To view or respond to this event, use WhatsApp on your primary device."` (found) redireciona usuários de dispositivo companion totalmente para fora da UI do Events v2. Essa é uma divisão deliberada: a entrega no nível de stanza é companion-safe, a interação no nível de feature é restrita ao dispositivo primário.

---

## 12. Lembretes e notificações

| Mecanismo | Gatilho | Found/Inferred |
|---|---|---|
| `hasReminder`/`reminderOffsetSec` (campos de wire 11/12 de `EventMessage`) | configurado pelo anfitrião, opções do picker Never / Time of event / 15 min / 30 min / 1 hour / 1 day before start | found (strings de UI); mapeamento de segundos inferred |
| Notificação de início sempre ativa | "Guests also get notified at the time of the event." (`str1a47`) | found — independente do lembrete personalizado, todo convidado recebe uma notificação quando o evento começa |
| "Allow precise event reminders" | prompt de permissão do SO para alarmes de horário exato | found |
| Notificações de atualização | texto varia conforme quais campos mudaram (§8) | found |
| Notificação de cancelamento | "%1$s canceled %2$s. See event" | found |
| Push MEX (`xwa2_notify_event_on_invite`/`_on_update`) | sincronização iniciada pelo servidor, independente da entrega pelo chat | found (§6.1) |

---

## 13. Feature flags

Nenhum ID numérico de feature flag controlando o comportamento do Events v2 foi recuperado nesta passagem — diferente dos call sites isolados de gatekeeper boolean/int de `WA_MESSAGE_SECRETS.md`, os acessores de injeção de dependência do pacote `eventsv2.*` (`C05T.A00(NNNNN)`, `C05Z.A00(NNNNN)`) são ids de lookup de componente/singleton, não leituras de flag, e nenhuma verificação boolean no estilo `AbstractC...Gatekeeper` ligada a uma flag numérica foi encontrada controlando a criação de evento, o RSVP, ou o redirecionamento de companion. As duas flags já documentadas para o caminho de criptografia de RSVP compartilhado permanecem as relevantes: **15791** (conversão de modifier LID→PN de resposta a evento em chats 1:1) e o maquinário de allowlist de companion/classificador de tipo de mensagem em `WA_MESSAGE_SECRETS.md` §15–16. Desconhecido se um kill-switch separado controla a própria UI do Events v2.

---

## 14. Baileys

Nenhum tratamento de envio ou recebimento de `eventMessage`/`eventInviteMessage`, e nenhuma criptografia de RSVP `encEventResponseMessage`, foi encontrado em `baron-baileys-v2` 1.5.17 além do que `WA_MESSAGE_SECRETS.md` §17 já documenta para o caminho de criptografia de add-on compartilhado (ele consegue decifrar um `encEventResponseMessage` recebido usando a tabela genérica de caso de uso, mas não existe código específico de evento para remetente ou modelo de evento). `eventMessage` e `eventInviteMessage` são, no mais, campos `Message` simples e enviáveis via `snowi.sendjson` com os campos escalares de §2/§3 — compor um não exige o crypto helper de forma alguma, apenas `encEventResponseMessage` (o RSVP) exige. Nenhum cliente GraphQL para as ops `www` do §6 existe no Baileys; elas exigem um caminho de POST GraphQL de `doc_id` persistido que não está implementado.

| Tópico | Baileys | Android |
|---|---|---|
| Enviar `eventMessage`/`eventInviteMessage` | campo `Message` simples, alcançável via `snowi.sendjson` | igual |
| Criptografar `encEventResponseMessage` | não implementado (somente decrypt, caminho de caso de uso genérico) | `DU9.ADr` + `MessageSecretCryptoHelper` |
| Events v2 GraphQL ops (§6) | não implementado | `GraphqlEventsDataSource` |
| MEX push sync (§6.1) | não implementado | `DefaultEventsNotificationRepository` |

---

## 15. Casos de erro / pegadinhas

| Sintoma | Causa | Nota |
|---|---|---|
| Falha ao decifrar RSVP / error 51 | chave da mensagem original errada, ou mismatch de namespace remetente/destino (PN vs LID) | compartilhado com o caminho de voto de enquete / comentário, ver `WA_MESSAGE_SECRETS.md` §18 |
| Evento visível na lista de Events mas nunca apareceu no chat | push MEX (`xwa2_notify_event_on_invite`) o sincronizou independentemente da entrega pelo chat | §6.1 |
| Localização/lista de convidados ausente para um convidado | ainda não fez RSVP (localização bloqueada), ou convidado não está nos contatos/histórico de chat do viewer (lista de convidados limitada) | §10 |
| Convidado removido ainda consegue fazer RSVP via link antigo | a remoção do convidado reseta o link para o registro *daquele* convidado, mas outros detentores do link já compartilhado não são afetados | §8, `str19ed` |
| "Can't change event" / evento bloqueado | o evento está suspenso por motivos de política, não meramente cancelado | §8 |
| Dispositivo companion não consegue abrir o evento | a interação do Events v2 é restrita ao dispositivo primário, mesmo que a própria stanza seja entregável a companion | §11 |
| `EventInviteMessage.status` (13) não pode ser parseado/produzido com precisão | classe enum não recuperável estaticamente; **não comprovado** ser idêntica ao vocabulário GraphQL `rsvp_status`/`status` | §3, §5.3 |

---

## 16. Distinções importantes

| Isto | Não isto |
|---|---|
| `eventMessage` (campo 75, base, 12 campos, inalterado desde antes da 41.6) | `eventInviteMessage` (campo 122, `DTQ`, 13 campos, o cartão ativo do "Events v2") |
| `encEventResponseMessage` (eco de RSVP criptografado E2E no chat) | `UpdateEventRsvp`/`JoinEventViaLink` (RSVP GraphQL em texto puro, visível ao servidor) |
| Cancelar (define `isCanceled`, encerra o RSVP, o evento permanece visível) | Excluir (remove da lista do anfitrião; os convites no chat permanecem, marcados como excluídos) |
| Excluir (iniciado pelo anfitrião, afeta a cópia do anfitrião + marca como excluído para os outros) | Sair (iniciado pelo convidado, o convidado para de ver futuras atualizações) |
| Suspender (bloqueio de moderação do servidor) | Cancelar (ação do anfitrião) |
| Remover convidado + resetar link (anfitrião, invalida a cópia do link *daquele* convidado) | Remover convite (anfitrião, antes de o convidado ter entrado) |
| enum de RSVP espelhado no wire `E2D`/`C9T8` (GOING=1, NOT_GOING=2, MAYBE=3, UNKNOWN=0) | enum de DB local `C9T6` (GOING=0, NOT_GOING=1, MAYBE=2, NO_RESPONSE=3) — ordenação diferente, mesmo conceito |
| enum de string GraphQL `rsvp_status` `C9U0` (`GOING`/`MAYBE`/`NOT_GOING`/`NO_RESPONSE`) | `EventInviteMessage.status` (campo 13) open enum int32 no wire — não recuperado, não comprovado que corresponda |
| Visibilidade da lista de convidados (limitada aos contatos do viewer) | Visibilidade do evento via link/QR (aberta a qualquer um que tenha o link) |

---

## 17. Fluxo completo (evento de grupo, criar → RSVP → atualizar)

```
[Host]                                   [WhatsApp server / GraphQL+MEX]           [Guest]
   │ CreateEvent (GraphQL, www)                   │                                   │
   │  chat_jid, description, location, cover──────▶ stores event, assigns eventId     │
   │◀──────────────────────────────────────────── eventId                             │
   │ compose eventInviteMessage (eventId,          │                                   │
   │   coverImageHandle, locationName, ...)        │                                   │
   │ <message type="event"> (E2E, chat plane)──────┼──────────────────────────────────▶ renders invite card
   │                                                │  xwa2_notify_event_on_invite      │
   │                                                ├──────────────────────────────────▶ event appears in
   │                                                │  (MEX push, independent of chat)    Events list too
   │                                                │                                   │ opens EventRsvpBottomSheet
   │                                                │                                   │ picks Going/Maybe/Not going
   │                                                │◀───────── UpdateEventRsvp (GraphQL, plaintext rsvp_status)
   │                                                │◀───────── encEventResponseMessage (E2E, chat plane)
   │  guest list / "Going" badge updates            │  xwa2_notify_event_on_update?     │
   │  (location now visible to guest)               │  (on edits)                       │
   │                                                │                                   │
   │ UpdateEvent (change location/time)─────────────▶ lastUpdatedTsUsec advances         │
   │                                                ├──────────────────────────────────▶ "Event date and location
   │                                                │                                      have been updated."
```

---

## 18. Unknowns

| Item | Status |
|---|---|
| Nomes dos membros do enum de `EventInviteMessage.status` (campo 13) | não recuperável estaticamente; as strings GraphQL `rsvp_status`/`status` (§5.3) são um análogo plausível, mas não confirmado |
| Segundos exatos de `reminderOffsetSec` por opção do picker | inferred (0/900/1800/3600/86400), pool de constantes não resolvido |
| Formato da URL de join-link / QR (`chat.whatsapp.com/event/...` ou similar) | não encontrado em strings ou intent filters do manifest nesta passagem |
| IDs numéricos de feature flag controlando criação/RSVP/redirecionamento de companion do Events v2 | não encontrado (ver §13) |
| Relação exata entre `EventInviteMessage.status` e os enums de app locais `C9T6`/`C9T8` | não rastreado |
| Comportamento de "Require approval to join" (`str1a34`) | string found; caminho de código não rastreado |
| Se os campos de history-sync `eventResponses`(61)/`eventAdditionalMetadata`(64) são preenchidos no history sync de saída, de entrada, ou em ambos | não rastreado |
