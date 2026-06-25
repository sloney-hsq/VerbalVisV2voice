Using only the supplied, source-verified literature evidence matrix, draft the Related Work section of an IEEE TVCG paper titled:

“VerbalVis: Supporting Analytical Intent Evolution through Full-Duplex Conversational Visual Analytics.”

Write four subsections:

2.1 Natural-Language Interaction for Visualization

2.2 LLM-Powered and Agentic Visual Analytics

2.3 Full-Duplex Conversational AI and Interruption

2.4 Sensemaking and Analytical Intent Evolution

Writing requirements:

1. Write argument-driven synthesis, not a paper-by-paper catalogue.
2. Each subsection should contain:

   - an opening statement defining the research area;
   - a synthesis of major approaches and evolution;
   - the closest systems to VerbalVis;
   - a precise limitation;
   - a final positioning sentence for VerbalVis.
3. Preserve important capabilities of prior work. Do not falsely state that prior systems lack:

   - conversational interaction;
   - iterative refinement;
   - multimodal interaction;
   - branching histories;
   - agent planning;

   when the evidence says otherwise.
4. Distinguish:

   - language interaction from LLM agency;
   - speech input from full-duplex interaction;
   - barge-in from analytical intent revision;
   - iteration after completed results from revision during active output;
   - provenance capture from active replanning.
5. Position VerbalVis as integrating:

   - native full-duplex spoken interaction;
   - mid-response barge-in;
   - analytical intent revision;
   - schema-grounded tool calls;
   - stale response/action invalidation;
   - dashboard-context grounding;
   - synchronized replanning across speech, tools, and visual state.
6. Describe Goal Shift, Hypothesis Correction, and Scope Narrowing as analytical categories used to study intent evolution. Do not claim they are runtime classifiers or hard-coded dispatch branches.
7. Do not claim VerbalVis is the first voice visualization system, the first full-duplex system, the first conversational visualization system, or the first iterative LLM visualization system.
8. The defensible novelty claim is the coupling of full-duplex interruption with analytical intent revision and dashboard replanning.
9. Use formal, restrained TVCG academic writing.
10. Every citation must be supported by the supplied evidence. Do not invent citations or BibTeX.
11. Target 1,700–2,200 words.
12. After the draft, provide:

    - a claim-to-citation audit;
    - potentially risky novelty claims;
    - missing evidence;
    - a shortened version under 1,400 words.

Related Work 的总体定位

这四个块是合理的，而且比“自然语言可视化—语音交互—LLM”这种按技术罗列的结构清楚得多。它们应当形成一条逐层收束的论证链：

NLI-for-Vis 讨论用户如何用语言表达分析意图；

LLM-Agent VA 讨论系统如何规划并执行复杂分析；

Full-Duplex Conversational AI 讨论用户何时能够修正系统、系统如何处理打断；

Sensemaking 解释为什么分析意图会持续演化，以及这种演化为什么需要被系统支持。

最后自然得到 VerbalVis 的研究缺口：

Existing work has separately advanced natural-language visualization, agentic data analysis, full-duplex speech interaction, and computational support for sensemaking. However, little work has examined how full-duplex interruption can serve as an interaction mechanism for revising analytical intent and synchronously replanning visual analytics actions.

这里最重要的是：不要声称 VerbalVis 首次支持自然语言、语音、打断或分析迭代。

你的新颖性来自这四者的耦合：

mid-response interruption → analytical intent revision → invalidation/replanning of analytical actions → synchronized dashboard update

你的当前测试程序也已经体现了这种系统定位：它不仅测量 TTFA 和端到端语音延迟，还评估工具名称、工具参数与多工具调用的正确性。因此 Related Work 也应区分“语音是否足够快”和“打断后分析动作是否正确”这两个层次。

推荐的正式章节结构

2 Related Work

2.1 Natural-Language Interaction for Visualization

2.2 LLM-Powered and Agentic Visual Analytics

2.3 Full-Duplex Conversational AI and Interruption

2.4 Sensemaking and Analytical Intent Evolution

建议总长度约 1,700–2,200 英文单词。每节写 3 个逻辑段落，而不是一篇论文一句话地罗列。

让其他 AI 查文献时，不要只摘摘要。要求它为每篇论文填写下面的 evidence matrix：

Dimension	需要提取的内容

Citation	作者、题目、年份、venue、DOI

Publication status	正式发表 / accepted / preprint

Primary task	查询、图表生成、分析、sensemaking、语音对话

User modality	text、speech、touch、GUI、multimodal

Output	chart、dashboard action、text answer、code、speech

Conversational structure	single-turn、multi-turn、branching、continuous

System initiative	reactive、mixed-initiative、proactive

Execution model	parsing、code generation、tool calling、agent planning

Interruption support	none、push-to-talk、barge-in、agent interruption

During-output revision	用户是否能在系统输出时修改请求

Cancellation semantics	是否取消旧语音、旧任务、旧工具调用

Visual-state grounding	是否感知当前 dashboard/view/mark/filter

Intent revision	是否讨论 goal/hypothesis/scope 的变化

History/provenance	是否记录、分支或回退

Evaluation	accuracy、latency、task performance、UX、qualitative study

Main limitation	与 VerbalVis 最相关的不足

Relation to VerbalVis	inherited capability / closest competitor / conceptual basis

# Part 1 — Natural-Language Interaction for Visualization and Visual Analytics

## Scope and interpretation

This review covers peer-reviewed work available through **June 25, 2026**. I prioritized IEEE VIS/TVCG, CHI, UIST, IUI, EuroVis, CUI, NAACL, and VLDB Journal papers, using publisher records and author-hosted papers to verify system behavior and DBLP/publisher metadata to verify publication details.

I distinguish four interaction properties that are sometimes conflated:

* **Multi-turn:** the next utterance can refer to an earlier completed utterance or visualization.
* **Multimodal:** language can be combined with pointing, touch, pen, or direct manipulation.
* **Always-listening:** the system continuously observes speech rather than waiting for an explicit push-to-talk command.
* **Full-duplex barge-in:** the user can speak while the system is producing a response, causing the system to stop stale output and invalidate work associated with the superseded intent.

`NR` below means **not reported in the paper or supplementary material inspected**. It does not prove that an unpublished implementation could not support the feature.

---

## 1. Evidence table: interpretation, ambiguity, state, and conversational context

| System                                               | Mapping from language to analytical intent                                                                                                                                                                                                                     | Ambiguity and underspecification                                                                                                                                                                | Effect on visualization state                                                                                                                      | Follow-up and contextual reference                                                                                                                                                                                                                                                |

| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |

| **Articulate** (2010)                                | Parses speech or text, classifies the query, identifies data attributes and analytical expressions, and uses visualization-selection heuristics to generate a graph.                                                                                           | Translates imprecise sentences into more explicit expressions, but offers limited interactive disambiguation. Its evaluation identified refined and follow-up queries as needed future support. | **Creates** a new visualization.                                                                                                                   | Maintains query history, but the published system is predominantly user-initiative rather than a persistent contextual dialogue.                                                                                                                                                  |

| **DataTone** (2015)                                  | Converts an utterance into candidate **data specifications**, executes data operations, constructs **visual specifications**, and ranks candidate visualizations. It recognizes attributes, aggregations, filters, comparisons, and chart-related constraints. | Makes ambiguity explicit through dropdowns, sliders, and other ambiguity widgets. User corrections become constraints that can influence subsequent interpretation.                             | Primarily **creates** a view; widgets subsequently **modify** the interpretation and result.                                                       | Limited cross-query carryover through stored constraints, but not a general discourse model for anaphora or intent revision. Speech was implemented as an input option but not evaluated and was treated as speech-to-text with additional recognition ambiguity. ([cond.org][1]) |

| **Eviza** (2016)                                     | Uses a probabilistic grammar whose rules are dynamically grounded in the active dataset and visualization. It supports filters, quantitative expressions, comparisons, temporal and spatial references, and view-oriented operations.                          | Combines probabilistic inference, domain awareness, defaults, and interactive widgets. It can expose alternative interpretations rather than silently forcing one parse.                        | Explicitly designed to **modify an existing visualization**, including filtering, selecting, navigating, and changing the current analytical view. | Supports an interactive query dialogue, including contextual and pragmatic references to the current view. Its unit of interaction nevertheless remains a completed utterance followed by a completed system update. ([ResearchGate][2])                                          |

| **Analyza** (2017)                                   | Uses schema metadata and semantic parsing to identify measures, dimensions, filters, sort orders, limits, comparisons, and temporal expressions. The interface reflects its interpretation back to the user.                                                   | Combines natural language with editable structured interface elements, allowing users to inspect and repair the interpreted query.                                                              | **Creates or modifies** dashboard slices and derived visual views.                                                                                 | Supports “sticky” context, nested queries, and transitions between conversational and structured interaction. ([谷歌研究][3])                                                                                                                                                         |

| **Evizeon / pragmatics-based interaction** (2018)    | Extends visualization-oriented language interpretation with discourse pragmatics rather than treating each query independently.                                                                                                                                | Resolves ellipsis, anaphoric references, deictic expressions, conjunctions, visualization-property references, and lexical cohesion using dialogue and visualization context.                   | Can **modify the active visualization** and produce a related view based on the discourse interpretation.                                          | Strong support for completed follow-up utterances such as references to prior attributes, visual elements, and prior query structure. ([dblp][4])                                                                                                                                 |

| **Orko** (2018)                                      | Maps speech or typed language to network-analysis operations, attributes, values, filters, path-related operations, and visual actions.                                                                                                                        | Uses ambiguity widgets, range controls, suggestions for incomplete operations, and conversational-centering rules.                                                                              | Primarily **modifies** the current network visualization.                                                                                          | Retains prior operations, attributes, and values so that follow-ups can continue, retain, or shift the conversational focus.                                                                                                                                                      |

| **Inferencing Underspecified Utterances** (2019)     | Treats incomplete utterances as partial analytical expressions and infers missing components using syntactic and semantic constraints from the data and visual-analysis domain.                                                                                | Specifically addresses omitted attributes, operations, and other underspecified query components.                                                                                               | A method for completing operations on an active analytical context rather than a separate visualization-authoring environment.                     | Context is used to complete the current utterance; this is not full-duplex or overlapping conversation.                                                                                                                                                                           |

| **FlowSense** (2020)                                 | Uses semantic parsing with special-utterance tags and placeholders for dataset names, columns, node types, and diagram entities, mapping commands to VisFlow dataflow functions.                                                                               | Explicitly displays recognized dataset and diagram terms, helping users detect grounding errors. It has less emphasis on conversational clarification than DataTone or Evizeon.                 | **Creates and modifies** nodes, operators, and connections in an existing dataflow diagram.                                                        | Context is primarily the current dataflow structure, not a general multi-turn discourse history. ([arXiv][5])                                                                                                                                                                     |

| **InChorus** (2020)                                  | Represents interaction through operations, parameters, targets, and instruments. Speech specifies operations or criteria while pen and touch identify marks, regions, axes, or other targets.                                                                  | Cross-modal grounding reduces verbal underspecification: phrases such as “remove these” obtain their referent from a pen or touch selection.                                                    | **Modifies** existing visualizations across multiple chart types.                                                                                  | Supports multimodal contextual references, but not persistent linguistic dialogue across multiple conversational turns. ([Microsoft][6])                                                                                                                                          |

| **NL4DV** (2021)                                     | Returns a JSON analytic specification containing detected attributes, analytical tasks, filters and operations, ambiguity information, and candidate Vega-Lite specifications.                                                                                 | Records attribute- and value-level ambiguity and can expose candidate interpretations through host-interface widgets.                                                                           | Normally **creates** candidate visualization specifications; a host editor can use the output to **modify** an existing specification.             | The original toolkit processes one-off utterances; contextual follow-ups were explicitly left for later work. ([arXiv][7])                                                                                                                                                        |

| **DataBreeze** (2021)                                | Combines speech with pen and touch to create and manipulate flexible unit visualizations. Language typically provides global operations or analytical predicates, while direct manipulation provides targets and spatial structure.                            | Uses cross-modal grounding instead of requiring every parameter and target to be stated verbally.                                                                                               | Both **creates and modifies** systematically bound and manually arranged views.                                                                    | Maintains interaction state through the visualization, but does not implement an explicit multi-turn linguistic discourse manager. ([arXiv][8])                                                                                                                                   |

| **Snowy** (2021)                                     | Builds on visualization-language interpretation and recommends possible next utterances using data interestingness and linguistic pragmatics.                                                                                                                  | Addresses discoverability and analytical underspecification by proposing relevant, executable questions rather than only asking the user to rephrase.                                           | A recommended utterance can **modify the current view or generate a related view**.                                                                | Supports sequential conversational analysis by recommending drill-downs and adjustments after the preceding query has completed. ([arXiv][9])                                                                                                                                     |

| **Conversational NL4DV** (2022)                      | Adds dialogue and query identifiers to NL4DV and automatically or manually classifies an utterance as standalone or as a follow-up. Follow-ups can augment, remove, or replace parts of the prior analytic specification.                                      | Exposes attribute- and value-level ambiguities in JSON; applications can resolve them using widgets or chatbot clarification before processing later follow-ups.                                | Both **creates and modifies** Vega-Lite-oriented analytic specifications.                                                                          | Explicit multi-turn support, including references to selected earlier queries and multiple simultaneous dialogue threads. All examples are organized as sequential, completed turns.                                                                                              |

| **Articulate+** (2022) and its IUI evaluation (2023) | Continuously listens to a multi-person analytical conversation, accumulates visualization properties, disambiguates requests, and can proactively generate charts without requiring every request to be addressed explicitly to the system.                    | Uses information distributed across ongoing human conversation to fill missing chart properties and interpret imprecise requests.                                                               | Primarily **creates** visualizations proactively.                                                                                                  | Introduces ambient and proactive context, but “always-listening” refers to continuous observation of human speech—not interruption of an active spoken system response or cancellation of an active visualization operation. ([ACM Digital Library][10])                          |

| **CoVis** (2026)                                     | Formulates conversational text-to-visualization as a multi-turn task, using accumulated dialogue context to produce textual, query, and visualization responses.                                                                                               | Later turns can supply information omitted from earlier turns; validation and correction are incorporated into the generation workflow.                                                         | Primarily **constructs** a visualization through multiple exchanges.                                                                               | Explicitly multi-turn, but still models a sequence of user and system turns rather than overlapping, mid-response revision. ([ACM Digital Library][11])                                                                                                                           |

### Main progression

The literature shows a clear progression:

1. **Heuristic and grammar-based translation:** Articulate, DataTone, and Eviza convert utterances into attributes, operations, data transformations, and visualization specifications.
2. **Contextual interpretation:** Analyza, Evizeon, and Orko incorporate dashboard state, dialogue focus, pragmatic references, and prior queries.
3. **Reusable analytic specifications:** NL4DV externalizes the interpretation as attributes, tasks, filters, ambiguities, and Vega-Lite specifications.
4. **Conversational refinement:** Snowy and conversational NL4DV support sequential follow-ups, recommendations, and ambiguity resolution.
5. **Multimodal grounding:** Orko, InChorus, and DataBreeze use touch, pen, selections, or visual state to resolve references that would be underspecified in speech alone.
6. **Ambient and proactive listening:** Articulate+ observes ongoing human conversation and may autonomously create a visualization.
7. **Recent multi-turn generation:** CoVis formalizes multi-turn text-to-visualization, but remains based on completed dialogue exchanges.

These stages align with the surveys’ broader classification of V-NLIs across query interpretation, data transformation, visual mapping, view transformation, human interaction, dialogue management, and presentation. ([arXiv][12])

---

## 2. Speech, multimodality, interruption, and invalidation audit

| Interaction family                                 | Representative systems                                                       | Role of speech                                                                                                                                   | System output model                                                                                  | Mid-output user interruption                                                                                                            | Can interruption invalidate an active visualization operation?                                                                                                                |

| -------------------------------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |

| **Text-first V-NLI**                               | DataTone, Eviza, Analyza, Evizeon, NL4DV, Snowy, conversational NL4DV, CoVis | No speech, or speech is not central to the evaluated interaction.                                                                                | A visualization, updated view, suggestion list, clarification widget, or completed chatbot response. | **NR.** Interaction assumes a submitted utterance followed by a result.                                                                 | **NR.** No operation-generation or intent-version protocol is described.                                                                                                      |

| **Speech as an alternative command channel**       | Articulate, FlowSense, NL4DV speech demonstration                            | Speech is converted to text and passed through substantially the same semantic parser used for typed input.                                      | Visual output; generally no streamed spoken explanation.                                             | **NR / not applicable to spoken system output.**                                                                                        | **NR.** A new recognized command may update state, but the papers do not describe canceling an already active operation.                                                      |

| **Speech grounded by direct manipulation**         | Orko, InChorus, DataBreeze                                                   | Speech is not merely a keyboard substitute. Pen, touch, selections, and spatial context supply targets or parameters omitted from the utterance. | Immediate visual state change.                                                                       | **NR.** These systems study multimodal input composition, not barge-in over system speech.                                              | **NR.** No stale-operation cancellation or result-rejection mechanism is reported.                                                                                            |

| **Always-listening and proactive speech**          | Articulate+                                                                  | Continuously observes human-human conversation and generates visualizations from explicit or implicit commands.                                  | Proactively generated visualizations and agent feedback.                                             | Continuous listening is supported, but the papers do **not** report interruption of an in-progress system utterance or response stream. | **NR.** No mechanism is reported for associating a visualization action with an intent version and invalidating it when the conversation changes. ([ACM Digital Library][10]) |

| **Full-duplex interruption required by VerbalVis** | Not found in the reviewed V-NLI corpus                                       | The system must listen while speaking and distinguish a corrective interruption from background speech or a backchannel.                         | Incrementally streamed speech plus asynchronous analytical tool calls and dashboard updates.         | Must stop or truncate stale output immediately.                                                                                         | Must cancel pending actions when possible and reject late results from superseded analytical intents.                                                                         |

A separate body of spoken-dialogue research studies interruption handling and overlapping conversation, and current realtime voice infrastructure explicitly supports canceling and truncating an in-progress spoken response. Those mechanisms, however, are not integrated with visualization-operation validity in the V-NLI systems reviewed here. ([ACM Digital Library][13])

---

## 3. Direct answers to the eight investigation questions

### 1. How is natural language mapped?

The dominant intermediate representations are:

* data attributes and values;
* analytical tasks such as filter, aggregate, compare, correlate, sort, and find extrema;
* data transformations or executable queries;
* visualization encodings and chart types;
* explicit visualization grammars such as Vega-Lite;
* view-level operations such as selection, navigation, highlighting, and filtering;
* dataflow nodes and edges in FlowSense;
* operation–parameter–target structures in multimodal systems.

The most useful precedent for VerbalVis is not a single parser. It is the general architectural pattern:

[

\text{utterance} \rightarrow

\text{grounded analytical specification} \rightarrow

\text{data/view operation} \rightarrow

\text{visual state}

]

DataTone, NL4DV, and FlowSense provide particularly clear examples of this intermediate-specification approach. ([cond.org][1])

### 2. How is ambiguity handled?

Four recurring strategies appear:

* **automatic inference:** choose the most probable attribute, value, task, or omitted component;
* **explicit widgets:** show dropdowns, sliders, candidate attributes, or candidate visualizations;
* **conversational clarification:** request or accept a later utterance that resolves the ambiguity;
* **multimodal grounding:** use a touch, pen selection, or current visual focus as the missing referent.

DataTone is the strongest precedent for ambiguity widgets; Evizeon and conversational NL4DV are stronger precedents for dialogue-context resolution; InChorus and DataBreeze show how direct manipulation can ground deictic expressions. ([cond.org][1])

### 3. Do systems create or modify visualizations?

Both models exist:

* **Creation-oriented:** Articulate, DataTone, NL4DV, Articulate+, and CoVis usually produce a new chart or specification.
* **Modification-oriented:** Eviza, Orko, FlowSense, and InChorus operate primarily on an existing view, network, or dataflow.
* **Hybrid:** Analyza, DataBreeze, Snowy, and conversational NL4DV can generate a new view or revise an existing analytical specification.

For VerbalVis, this distinction should be explicit at the tool level: an interruption may revise a pending creation command, an already-applied global filter, or a view-local operation.

### 4. Are follow-ups and contextual references supported?

Yes, but with different forms of context:

* **visual context:** current attributes, selected marks, filters, or chart state;
* **dialogue context:** previous utterance, previous query specification, or conversational focus;
* **multimodal context:** the object currently touched, selected, or pointed at;
* **ambient conversational context:** properties mentioned across multi-person discussion.

Evizeon and conversational NL4DV provide the clearest dialogue-state precedents. Orko contributes conversational focus, while Articulate+ contributes ambient conversational context. ([dblp][4])

### 5. Are language and direct manipulation combined?

Yes. Orko, InChorus, and DataBreeze demonstrate that speech becomes substantially more expressive when another modality identifies the target. “Remove these,” for example, is usable when “these” is grounded in a pen or touch selection. ([arXiv][14])

### 6. Is speech merely a substitute for typed text?

Often, yes:

* Articulate and FlowSense use speech recognition as an input front end to a language parser.
* NL4DV demonstrates that speech can be added around the toolkit, but speech is not part of its core dialogue architecture.

In Orko, InChorus, DataBreeze, and Articulate+, speech is more consequential because it is combined with touch or ambient conversational context. Nevertheless, none of these systems establishes the concurrent speech-output control required by VerbalVis.

### 7. Can the user interrupt while the system is producing output?

Across the peer-reviewed visualization systems reviewed here, I found **no reported implementation or evaluation of semantic barge-in over an incrementally spoken system response**.

This result should be worded carefully:

* Most V-NLIs do not produce long spoken responses at all.
* “Conversational” generally means a sequence of completed turns.
* “Always-listening” means that the microphone remains active or the system observes ongoing conversation.
* Neither property necessarily means that a user utterance stops an active system response.

### 8. Can interruption invalidate an active visualization operation?

I found **no reported mechanism** in this literature that jointly:

1. detects a corrective interruption;
2. stops stale speech;
3. identifies visualization or data operations belonging to the superseded intent;
4. cancels those operations or rejects their late results;
5. reinterprets the interruption against the last committed dashboard state; and
6. synchronizes subsequent speech and visualization output with the revised analytical direction.

This is a stronger and more defensible gap than simply claiming that prior systems “do not support speech interruption.”

---

## 4. Recommended positioning for VerbalVis

The evidence supports positioning VerbalVis against three increasingly capable baselines:

| Baseline interaction model               | Supported capability                                                                      | Missing capability addressed by VerbalVis                                                                                    |

| ---------------------------------------- | ----------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |

| **Command-based V-NLI**                  | A complete utterance becomes a visualization query or command.                            | Intent cannot change while the response is underway.                                                                         |

| **Contextual or multi-turn V-NLI**       | A later utterance can refine an earlier completed query or view.                          | Refinement occurs after a turn boundary and does not invalidate concurrent work.                                             |

| **Multimodal or always-listening V-NLI** | Speech is grounded in touch, pen, visual state, or ambient conversation.                  | Continuous input does not by itself provide response cancellation, stale-operation invalidation, or synchronized replanning. |

| **VerbalVis**                            | The user can revise analytical intent while the assistant is speaking or executing tools. | Treats interruption as a state-changing analytical event rather than only a turn-taking event.                               |

---

## 5. Defensible Related Work gap statement

The following paragraph is suitable as the closing paragraph of the **Natural-Language Interaction for Visualization** subsection.

Existing visualization-oriented natural-language interfaces translate user utterances into data attributes, analytical tasks, transformations, filters, and visual encodings, while more advanced systems additionally support ambiguity resolution, contextual references, multimodal grounding, and multi-turn refinement. Systems such as Eviza and Orko modify an existing visual state, NL4DV externalizes language interpretation as structured analytic specifications, and conversational or always-listening interfaces extend interaction across successive utterances or ongoing human discussion. Nevertheless, these systems generally organize interaction around completed user–system turns: an utterance is interpreted, a visualization operation is executed, and a subsequent utterance may then refine the resulting state. Across the reviewed literature, we found no mechanism that treats a mid-response interruption as an analytical state revision that must simultaneously stop stale speech, invalidate pending visualization operations, reinterpret the revised intent, and synchronize the dashboard with the new analytical direction. VerbalVis addresses this gap by coupling full-duplex conversational control with intent-versioned analytical actions, enabling users to revise an evolving analysis while the system is still responding.

The first two sentences are supported by the command, contextual, multimodal, and always-listening systems above; the final distinction is specifically about **concurrent response control and analytical-operation validity**, rather than simply whether prior systems accept speech or follow-up queries. ([cond.org][1])

---

## 6. Verified BibTeX

The bibliography contains **20 entries**, including all principal systems in the evidence table, the underspecification method, the Articulate+ evaluation, CoVis, the empirical utterance study, and three major survey/overview papers. Metadata was cross-checked against ACM, IEEE, Springer, ACL Anthology, Eurographics, and DBLP records. ([dblp][15])

[Download the verified BibTeX file](sandbox:/mnt/data/verbalvis_part1_vnli_verified.bib)

Included citation keys:

```text

sun2010articulate

gao2015datatone

setlur2016eviza

dhamdhere2017analyza

hoque2018pragmatics

srinivasan2018orko

setlur2019underspecified

yu2020flowsense

srinivasan2020inchorus

narechania2021nl4dv

srinivasan2021databreeze

srinivasan2021snowy

srinivasan2021utterances

mitra2022conversational

tabalba2022articulateplus

tabalba2023alwayslistening

song2026covis

srinivasan2017nli

voigt2022whyhow

shen2023survey

```

[1]: https://www.cond.org/DataTone-cr.pdf
[2]: https://www.researchgate.net/publication/319463429_Natural_Language_Interfaces_for_Data_Analysis_with_Visualization_Considering_What_Has_and_Could_Be_Asked?utm_source=chatgpt.com
[3]: https://research.google.com/pubs/archive/45791.pdf
[4]: https://dblp.org/db/journals/tvcg/tvcg24?utm_source=chatgpt.com
[5]: https://arxiv.org/abs/1908.00681?utm_source=chatgpt.com
[6]: https://www.microsoft.com/en-us/research/wp-content/uploads/2020/02/InChorus-CHI2020.pdf?utm_source=chatgpt.com
[7]: https://arxiv.org/abs/2008.10723?utm_source=chatgpt.com
[8]: https://arxiv.org/abs/2004.10428?utm_source=chatgpt.com
[9]: https://arxiv.org/abs/2110.04323?utm_source=chatgpt.com
[10]: https://dl.acm.org/doi/fullHtml/10.1145/3543829.3544534?utm_source=chatgpt.com
[11]: https://dl.acm.org/doi/abs/10.1007/s00778-025-00954-4?utm_source=chatgpt.com
[12]: https://arxiv.org/abs/2109.03506?utm_source=chatgpt.com
[13]: https://dl.acm.org/doi/fullHtml/10.1145/3652988.3673916?utm_source=chatgpt.com
[14]: https://arxiv.org/abs/2001.06423?utm_source=chatgpt.com
[15]: https://dblp.org/db/conf/uist/uist2015.html?utm_source=chatgpt.com
# Part 2 — LLM-Powered and Agentic Visual Analytics

## 1. Scope and coding criteria

The search identifies three broad generations of work:

1. **LLM as chart-code generator**: natural language is translated into visualization code.
2. **LLM as authoring collaborator**: the model transforms data, edits visual specifications, and supports iterative refinement.
3. **LLM as analytical agent**: the model plans multiple analysis steps, invokes tools or code, interprets results, manages insights, or proactively acts on a visualization interface.

The evidence matrix uses conservative definitions:

* **Live-state grounding** means that the model or agent receives the current visualization, dashboard, interaction log, UI state, or executable analytical state—not merely the preceding chat transcript.
* **Mid-execution intervention** means that users can revise the active intent before the current response, code execution, or interface action sequence has completed.
* **Stale-work cancellation** means that obsolete speech, plans, tool calls, queued actions, or UI operations are explicitly invalidated after an intent revision. Producing another result in the next turn does not count.
* **NR** means the capability was not reported or evaluated; it does not mean that implementation would be technically impossible.

---

## 2. Classification of the literature

### A. Natural-language-to-visualization generation

**Chat2VIS** translates natural-language requests into executable visualization code using general-purpose LLMs. Its primary contribution is chart generation rather than sustained analytical reasoning, dashboard-state management, or multi-step exploration. ([arXiv][1])

**LIDA** goes beyond a single prompt-to-code call by decomposing automatic visualization generation into modules such as data summarization, goal generation, visualization generation, code execution, refinement, and infographic generation. Nevertheless, its central unit of work remains the production and refinement of individual visualizations. ([ACL Anthology][2])

**MatPlotAgent** adds an agentic loop around chart generation: it generates code, executes and debugs it, inspects the rendered visual output, and applies visual-feedback-based corrections. This represents agentic chart creation, but its primary evaluation is visualization-generation performance rather than open-ended visual analysis. ([dblp][3])

**Conclusion for A:** Code execution, visual feedback, and self-correction already distinguish recent systems from simple NL-to-spec translation. However, the analytical object is still usually a requested chart rather than an evolving investigation grounded in a persistent dashboard.

---

### B. LLM-assisted visualization authoring

**Data Formulator** introduced concept-driven visualization authoring in which users specify semantic concepts and visual encodings while the system uses AI to derive the required data transformations. It is not merely a text-to-chart generator: users retain control over the visual mapping, while the system handles otherwise burdensome transformation code. ([dblp][4])

**Data Formulator 2** substantially extends this model. It combines graphical authoring with natural-language instructions, generates and executes data-transformation code, exposes transformed data and explanations, repairs some execution failures, and stores results in tree-structured **data threads**. Users can return to an earlier result, revise a prompt, rerun an operation, or fork a new analytical-authoring branch. ([arXiv][5])

**DynaVis** uses LLMs to synthesize contextual user-interface widgets for visualization editing. Rather than forcing every refinement through another text prompt, it converts an underspecified language request into interactive controls through which users can inspect and adjust parameters. This is an important human-agency pattern: use language to create manipulable interfaces rather than treating the generated result as final. ([dblp][6])

**Conclusion for B:** Iterative visualization authoring and mixed GUI–language interaction are already well established. VerbalVis therefore should not claim that existing LLM visualization systems are non-iterative.

---

### C. Conversational data analysis

**Conversational AI Threads / AI Threads** investigates explicit conversational threads for multidimensional data analysis. Users can maintain multiple analytical contexts rather than forcing all questions into one linear conversation. As of June 25, 2026, the version located in this search remained an arXiv preprint rather than a verified peer-reviewed publication. ([arXiv][7])

**Data Has Entered the Chat** is particularly important as empirical evidence rather than as a new agent architecture. Through two studies involving 50 data workers, it examines how people use a generative-AI technology probe for exploratory visual analysis. The reported interactions include analytical requests, visualization edits, elaborations, enrichments, directives, and recurring refinement and explanation loops. It therefore demonstrates that conversational visual analysis naturally involves iterative intent development rather than isolated chart requests. ([卡罗莱纳数字库][8])

**WaitGPT** exposes the model’s streamed analysis code as line-level executable operations. Users can inspect intermediate operations, modify them, rerun selected parts, and resume execution. It is one of the strongest precedents for intervention during a model-generated analysis process. However, the paper does not establish full-duplex spoken interruption or coordinated cancellation of speech and visualization actions; an explicit stop mechanism is identified as future work. ([arXiv][9])

**Conclusion for C:** Conversational systems increasingly expose analytical process and history, but most interaction is still organized around textual turns, completed operations, or visible code checkpoints.

---

### D. Agent planning and tool execution

**InsightPilot** uses an LLM to interpret an analytical question and issue a sequence of analysis actions to an insight engine. It therefore moves beyond chart generation toward automated multi-step data exploration, although users mainly specify a high-level question and receive the resulting exploration. ([ACL Anthology][10])

**LightVA** is one of the clearest examples of an LLM-based visual analytics agent. Its architecture separates planning, execution, and control; decomposes analytical objectives into tasks; executes analysis and visualization code; and incorporates reflection, error handling, rollback, and task-state management. Users can inspect or modify task plans, visualization specifications, generated insights, and pending tasks. This supports meaningful human oversight, but intervention is mainly exposed at task or interface checkpoints rather than as interruption of a currently executing spoken-and-tool response. ([arXiv][11])

**InsightLens** combines a data-science agent with code execution and additional agents for insight extraction and insight management. It exposes evidence, code, charts, chronological history, and topical organization so that users can inspect how conclusions were produced. It supports iterative conversational analysis and navigation through analytical results, but does not report cancellation of an active plan after a mid-response intent revision. ([arXiv][12])

**ProactiveVA** grounds an LLM-based UI agent in current visualizations, data, interaction logs, and interface widgets. The agent perceives the analytical state, plans subtasks, reasons and acts through the interface, reflects on action outcomes, and proposes or executes next steps. Users can control the degree of proactivity and choose whether to apply recommendations. Notably, its study reports that a participant wanted to intervene while the agent was progressing, indicating that mid-process steering remained an unresolved interaction need. ([arXiv][13])

**Conclusion for D:** Planning, code execution, tool use, reflection, and even UI-level action are no longer sufficient novelty claims by themselves. The more defensible question is how users can regain control while those mechanisms are active.

---

### E. Insight management and analytical history

Relevant history models differ substantially:

* **Data Formulator 2** stores transformed datasets and visualizations as a tree of completed authoring states. Users can branch, revise, rerun, and backtrack. ([arXiv][5])
* **AI Threads** separates multiple conversational analysis contexts, reducing contamination between distinct lines of inquiry. ([arXiv][7])
* **InsightLens** provides chronological and topic-oriented organization of generated insights and supporting evidence. Its history is primarily navigational rather than a fully executable branching workspace. ([arXiv][12])
* **LightVA** maintains task and execution state, supports rollback after failures, and lets users remove or revise pending analytical tasks. ([arXiv][11])
* **Tree-of-Analysis** represents conversational visual analysis as an explicit tree in which analytical questions and model outputs form navigable branches. It addresses orientation and exploration across completed conversational states, rather than interruption of an active tool-execution episode. ([ACM Digital Library][14])
* **StepMIND** represents AI-generated data-analysis pipelines in a stepwise and bidirectional form so users can inspect and explain how analytical outputs were produced. It contributes process transparency and controllability, but is not a full-duplex interruption architecture. ([ACM Digital Library][15])

**Conclusion for E:** Branching history is not absent from the literature. The distinction needed for VerbalVis is between:

* revising a **stored completed state**, and
* revising the analytical intent while the current response and its associated actions are still unfolding.

---

### F. Proactive or autonomous visual analytics

**LEVA** integrates LLM assistance across visual analytics stages, including system-state interpretation, recommendation, exploration support, and history summarization. It is grounded in the current VA environment and uses recommendations to augment rather than fully replace the analyst. ([arXiv][16])

**AVA** explores autonomous visualization agents that inspect rendered visual outputs and iteratively adjust visualization parameters according to a high-level objective. Its distinctive contribution is visual-perception-driven decision-making, but the loop is primarily agent-led after the objective has been supplied. ([arXiv][17])

**InsightPilot** and **LightVA** automate portions of analytical decomposition and execution, although their degree of autonomy and user oversight differs. ([ACL Anthology][10])

**ProactiveVA** is the closest example of an agent that observes an active visual analytics interface and proactively continues analysis through UI actions. Its controls for recommendation frequency and action acceptance are strong human-agency mechanisms, but they do not yet constitute immediate barge-in plus invalidation of an already active multimodal response. ([arXiv][13])

---

## 3. Condensed evidence matrix

**Legend:** Y = explicitly supported; P = partial or checkpoint-based; N = explicitly absent; NR = not reported.

| System                                       | Cat.  | Code-only or multi-step                       | Tools, planning, reflection                                            | Iterative refinement         | Branch/backtrack                                    | Live dashboard or execution state                      | Mid-execution intervention                        | Cancellation of stale work                                                          | Human agency                                                          | Evaluation focus                                     |

| -------------------------------------------- | ----- | --------------------------------------------- | ---------------------------------------------------------------------- | ---------------------------- | --------------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------- | ----------------------------------------------------------------------------------- | --------------------------------------------------------------------- | ---------------------------------------------------- |

| **Chat2VIS** ([arXiv][1])                    | A     | Primarily chart-code generation               | Prompted code generation                                               | P: repeat prompts            | N                                                   | N                                                      | NR                                                | NR                                                                                  | User specifies request and inspects chart                             | Generation quality and examples                      |

| **LIDA** ([ACL Anthology][2])                | A/B   | Modular chart-generation pipeline             | Goal generation, code generation, execution, refinement                | Y                            | N                                                   | P: dataset and generated artifact                      | N                                                 | NR                                                                                  | Users select goals and refine outputs                                 | System capability and generation                     |

| **MatPlotAgent** ([ACL 2024][18])            | A/D   | Agentic chart generation                      | Code execution, debugging, visual feedback, self-correction            | P: internal agent loop       | N                                                   | P: rendered chart                                      | N                                                 | NR                                                                                  | User supplies target chart; limited process steering                  | Chart-generation benchmark                           |

| **Data Formulator** ([dblp][4])              | B     | Transformation plus visualization authoring   | AI-generated data transformations                                      | Y                            | N                                                   | P: current dataset and chart                           | N                                                 | NR                                                                                  | Concept binding and direct visual specification                       | Authoring tasks and user study                       |

| **Data Formulator 2** ([arXiv][5])           | B/E   | Iterative authoring with transformation code  | Code generation, execution, repair, contextual reuse                   | Y                            | **Y: tree, fork, rerun, revise**                    | P: selected data-thread state                          | N: revisions occur across completed states        | NR for in-flight work                                                               | GUI+NL, code/data inspection, direct manipulation                     | Iterative exploratory-authoring study                |

| **DynaVis** ([ACM Digital Library][19])      | B     | Visualization editing                         | LLM-synthesized UI controls and edit operations                        | Y                            | N                                                   | Y: current visualization                               | N                                                 | NR                                                                                  | Generated widgets preserve direct manipulation                        | Editing tasks and user study                         |

| **AI Threads** ([arXiv][7])                  | C/E   | Conversational chart creation and analysis    | Thread-specific conversational context                                 | Y                            | **Y: multiple threads**                             | P: conversational/chart context                        | N                                                 | NR                                                                                  | Users create and switch analytical threads                            | Crowd study and expert interviews; preprint          |

| **Data Has Entered the Chat** ([卡罗莱纳数字库][8]) | C     | Empirical technology probe                    | Code-generating GenAI probe                                            | Y: observed refinement loops | P: threads in probe                                 | P                                                      | N studied                                         | Not studied                                                                         | Users direct, edit, elaborate, and question results                   | Open-ended exploratory visual analysis               |

| **WaitGPT** ([arXiv][9])                     | C/D/E | Streamed multi-step code analysis             | Line-level execution, sandbox, rerun, resume                           | Y                            | P: operation history, not full analytical branching | Y: live code/runtime state                             | **P/Y: inspect and modify streamed operations**   | **N: explicit stopping left as future work**                                        | Intermediate operations remain editable                               | Controlled tasks plus free exploration               |

| **InsightPilot** ([ACL Anthology][10])       | D/F   | Automated multi-step exploration              | LLM selects and sequences analytical actions                           | P                            | N                                                   | N/P: analytical engine, not live dashboard interaction | N                                                 | NR                                                                                  | User defines high-level question                                      | User study and analytical cases                      |

| **LightVA** ([arXiv][11])                    | D/E/F | Multi-step visual analysis                    | Planner, executor, controller, code, reflection, rollback              | Y                            | P: task graph and rollback                          | P: views, code, and task state                         | P: plans/pending tasks editable at boundaries     | P: pending/failed tasks removable; no reported in-flight cross-channel invalidation | Users inspect and override plans, code, views, insights               | Technical tests, scenarios, expert study             |

| **InsightLens** ([arXiv][12])                | C/D/E | Multi-step conversational analysis            | ReAct-style DS agent, code execution, extraction and management agents | Y                            | P: navigate history, no executable branching        | P: conversation, code, evidence, charts                | N                                                 | NR                                                                                  | Evidence inspection and insight navigation                            | Technical evaluation and analyst study               |

| **LEVA** ([arXiv][16])                       | E/F   | Mixed-initiative VA assistance                | State interpretation, recommendations, summarization                   | Y                            | P: history retracing                                | **Y**                                                  | N                                                 | NR                                                                                  | Recommendations supplement analyst activity                           | Scenarios and user study                             |

| **AVA** ([Wiley在线图书馆][20])                   | F     | Autonomous iterative visualization refinement | Visual perception and action loop                                      | P: agent-led iteration       | N                                                   | **Y: rendered visual output**                          | N                                                 | NR                                                                                  | User sets objective; agent evaluates result                           | Proof-of-concept cases and expert feedback           |

| **ProactiveVA** ([arXiv][13])                | D/F   | Autonomous multi-step UI exploration          | Perception, planning, ReAct, UI actions, reflection                    | Y                            | P: history retained                                 | **Y: UI, data, views, interaction logs**               | **N in current design; requested by participant** | NR                                                                                  | Preview/apply controls, proactivity settings, independent exploration | Algorithm evaluation, cases, expert and user studies |

The complete matrix is also available as a spreadsheet-compatible CSV:

[Download the evidence matrix](sandbox:/mnt/data/verbalvis_part2_evidence_matrix.csv)

---

## 4. What the matrix shows

### 4.1 Iteration is not the research gap

Data Formulator 2, DynaVis, AI Threads, InsightLens, LightVA, and WaitGPT all provide forms of iterative refinement. Data Formulator 2 and AI Threads additionally make non-linear history explicit. Therefore, statements such as “existing systems only generate a visualization in one shot” would be incorrect. ([arXiv][5])

### 4.2 Agent planning and code execution are not sufficient novelty claims

InsightPilot sequences analysis actions; LightVA has planner–executor–controller roles and reflection; InsightLens uses multiple specialized agents and code execution; ProactiveVA plans and operates a live UI; MatPlotAgent uses execution and visual-feedback correction. ([ACL Anthology][10])

Consequently, VerbalVis should not be positioned simply as “an LLM agent that calls visualization tools.”

### 4.3 History management exists, but at different temporal granularities

Most history mechanisms preserve **completed outputs**:

* a transformed dataset and chart node,
* a finished conversation turn,
* a completed insight,
* an executed task,
* or a previous analysis branch.

They generally answer:

> “How can the user revisit or continue from something the system has already produced?”

VerbalVis instead asks:

> “What happens when the user revises the analytical goal before the system has finished producing and acting on the current answer?”

This is a difference in **temporal interaction semantics**, not merely in interface modality.

### 4.4 Live dashboard grounding is emerging, but not universal

LEVA and ProactiveVA explicitly reason from the active visual analytics environment. AVA perceives rendered visualization output, while LightVA and InsightLens preserve parts of the analytical execution state. Other systems primarily ground the model in a dataset, prompt history, generated code, or a selected authoring node. ([arXiv][16])

Thus, “dashboard grounding” alone is also not a categorical gap. The stronger distinction is grounding combined with **ongoing response control and state invalidation**.

### 4.5 Mid-execution control is the sparsely addressed dimension

WaitGPT is the most important qualification to any novelty claim: it makes streamed analytical operations visible and editable before the overall analysis is finished. However, it is code-centric, not full-duplex spoken interaction, and it does not report coordinated stopping of active speech, code, and visualization operations after a revised intent. ([arXiv][9])

LightVA permits users to modify plans and remove pending tasks, but these controls operate primarily on exposed task structures and checkpoints. ProactiveVA acts on live UI state, yet its own study surfaced a desire for intervention while the agent was progressing. ([arXiv][11])

This makes **cross-channel invalidation** the clearest underexplored mechanism:

1. stop obsolete spoken output;
2. reinterpret the user’s revised analytical intent;
3. invalidate tool calls or dashboard actions derived from the previous intent;
4. preserve already valid analytical state;
5. replan from the revised goal;
6. synchronize the new plan with the dashboard and subsequent speech.

---

## 5. Data Formulator 2 versus VerbalVis

Data Formulator 2 should be treated as a strong adjacent system, not as a simplistic turn-based baseline.

| Dimension                     | Data Formulator 2                                                                               | VerbalVis research target                                                                                      |

| ----------------------------- | ----------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |

| **Primary activity**          | Iterative visualization authoring with AI-generated data transformations                        | Exploratory visual analysis through full-duplex spoken collaboration                                           |

| **Interaction composition**   | Blended GUI plus natural-language authoring                                                     | Speech, realtime conversational control, schema-grounded tools, and dashboard interaction                      |

| **Persistent state unit**     | A node containing a transformed dataset, visualization, code, prompt, and explanation           | A dashboard and conversational episode with active speech, analytical intent, tool execution, and visual state |

| **Iteration**                 | Follow-up instructions refine a selected completed result                                       | Follow-up utterances may arrive before the current response or action sequence completes                       |

| **Branching**                 | Users return to an earlier node and fork a new data thread                                      | A barge-in may invalidate the active direction and initiate a revised analytical trajectory                    |

| **Backtracking**              | Earlier completed states remain available and can be rerun or revised                           | The system preserves valid prior dashboard state while withdrawing obsolete, not-yet-committed actions         |

| **Replanning trigger**        | User selects a previous state and submits another authoring instruction                         | User interrupts ongoing speech with a revised goal, hypothesis, or data scope                                  |

| **Execution control**         | Transformation code is generated, run, inspected, and sometimes repaired                        | Speech and dashboard tools are coordinated; stale actions must be cancelled, ignored, or superseded            |

| **Human agency**              | Inspect data/code/explanations, directly manipulate visual fields, revise prompts, fork history | Interrupt immediately, redirect the active analysis, and regain control without waiting for turn completion    |

| **Central research question** | How can AI support iterative and branching visualization creation?                              | How should a VA system respond when analytical intent evolves during an ongoing multimodal response?           |

Data Formulator 2’s data threads capture **versioned authoring provenance**: users work from completed nodes and deliberately create new branches. VerbalVis addresses a finer temporal interval. The revision occurs while speech may still be playing and while tool-derived dashboard operations may already be planned, queued, or executing. The system must determine which previous effects remain valid and which have become stale.

A claim-safe formulation is:

> Data Formulator 2 supports iterative and branching visualization authoring across persistent completed states. VerbalVis studies a complementary temporal problem: analytical intent revision during an ongoing spoken response, requiring synchronized interruption and replanning across conversational output and dashboard actions.

This wording credits Data Formulator 2’s genuine iterative contribution while clearly distinguishing VerbalVis.

---

## 6. Human-agency mechanisms found in the literature

Across these systems, human agency is preserved through several recurring patterns:

* **Specification control:** users define fields, concepts, encodings, or high-level analytical objectives.
* **Process visibility:** users inspect generated code, intermediate operations, evidence, task plans, or insight provenance.
* **Direct manipulation:** generated charts remain editable through GUI controls or synthesized widgets.
* **Plan oversight:** users approve, revise, reorder, or remove proposed tasks.
* **History navigation:** users return to earlier results, switch threads, compare insights, or create branches.
* **Autonomy controls:** users determine whether proactive suggestions are merely displayed or automatically applied.

The agentic-visualization design-pattern literature similarly frames autonomy as a coordination problem involving agent roles, communication, and relationships with human analytical control—not as a binary choice between manual and autonomous analysis. ([Pure][21])

The recent agentic visual analytics survey organizes systems around roles such as planning, creation, review, and context management. It is useful as a framing source, but its June 2026 version is a preprint and should be cited as such rather than presented as peer-reviewed evidence. ([arXiv][22])

VerbalVis adds another agency mechanism:

> **temporal veto power**—the user can withdraw or revise an instruction before the system finishes acting on it.

That notion is stronger than merely editing the result afterward.

---

## 7. Evaluation implications for VerbalVis

The literature uses several different evaluation targets:

* **Chart-generation accuracy or fidelity:** Chat2VIS and MatPlotAgent.
* **Visualization-authoring effectiveness:** Data Formulator, Data Formulator 2, and DynaVis.
* **Analytical workflow and open-ended exploration:** Data Has Entered the Chat, WaitGPT, InsightLens, LightVA, and ProactiveVA.
* **Autonomous-agent technical performance:** InsightPilot, AVA, LightVA, and ProactiveVA.

For VerbalVis, a chart-generation benchmark alone would not test the claimed contribution. The evaluation should capture whether interruption changes the quality and efficiency of exploratory analysis. Defensible measures include:

* interruption-to-speech-stop latency;
* interruption-to-dashboard-consistency latency;
* number of stale actions executed after a revision;
* accuracy of retaining versus invalidating prior actions;
* time required to revise an analytical direction;
* perceived control and recoverability;
* number and diversity of analytical revisions;
* exploration breadth and analysis coverage;
* errors caused by asynchronous speech and dashboard state.

A turn-based comparison condition should allow the same tools and underlying model, while requiring users to wait until the response or operation completes. This isolates the effect of full-duplex intervention from general LLM capability.

---

## 8. Verified bibliography files

The accompanying BibTeX file contains 19 entries covering the core systems and recent framing papers. Peer-reviewed venue and DOI information is included where available. **AI Threads** and the **2026 agentic visual analytics survey** are explicitly marked as preprints.

[Download the verified BibTeX](sandbox:/mnt/data/verbalvis_part2_verified_references.bib)

[Download the full evidence matrix CSV](sandbox:/mnt/data/verbalvis_part2_evidence_matrix.csv)

The bibliography includes:

`Chat2VIS`, `LIDA`, `Data Formulator`, `Data Formulator 2`, `DynaVis`, `AI Threads`, `Data Has Entered the Chat`, `WaitGPT`, `InsightPilot`, `LightVA`, `LEVA`, `InsightLens`, `AVA`, `MatPlotAgent`, `ProactiveVA`, `Agentic Visualization`, `Tree-of-Analysis`, `StepMIND`, and the 2026 agentic visual analytics survey.

## Recommended gap statement

Existing LLM-powered visual analytics systems increasingly support iterative refinement, data transformation, code execution, task planning, self-correction, insight management, branching histories, and proactive interface actions. Some systems also expose intermediate analytical operations or ground agents in the current visualization environment. However, these interactions usually remain organized around completed turns, authoring states, or task checkpoints, and provide limited support for revising analytical intent while a spoken response and its associated analytical actions are still in progress. VerbalVis addresses this temporal coordination gap by enabling full-duplex spoken interruption and synchronizing the revised intent across response termination, stale-action invalidation, schema-grounded replanning, and live dashboard state.

[1]: https://arxiv.org/abs/2302.02094
[2]: https://aclanthology.org/2023.acl-demo.11/?utm_source=chatgpt.com
[3]: https://dblp.org/pid/186/8414
[4]: https://dblp.org/pid/35/6081-2.html
[5]: https://arxiv.org/html/2408.16119v1
[6]: https://dblp.org/pid/217/9223
[7]: https://arxiv.org/abs/2311.05590
[8]: https://cdr.lib.unc.edu/concern/articles/c534g4943
[9]: https://arxiv.org/html/2408.01703v1
[10]: https://aclanthology.org/2023.emnlp-demo.31/
[11]: https://arxiv.org/html/2411.05651
[12]: https://arxiv.org/html/2404.01644v1
[13]: https://arxiv.org/html/2507.18165v1
[14]: https://dl.acm.org/doi/10.1145/3772318.3791690
[15]: https://dl.acm.org/doi/10.1145/3742413.3789070
[16]: https://arxiv.org/abs/2403.05816
[17]: https://arxiv.org/abs/2312.04494
[18]: https://2024.aclweb.org/program/finding_papers/?utm_source=chatgpt.com
[19]: https://dl.acm.org/doi/fullHtml/10.1145/3613904.3642639
[20]: https://onlinelibrary.wiley.com/doi/full/10.1111/cgf.15093
[21]: https://pure.au.dk/portal/en/publications/agentic-visualization-extracting-agent-based-design-patterns-from/
[22]: https://arxiv.org/abs/2604.15813
# Part 3：Full-Duplex Conversational AI

**检索截止时间：2026 年 6 月 25 日。**

## 一、核心结论

现有工作可以分为三条尚未真正汇合的研究线：

1. **全双工语音模型**研究系统如何在说话时继续听、处理重叠语音、预测话轮、接受 barge-in，并缩短响应延迟。
2. **HCI 与对话协调研究**关注用户如何理解系统的让步、忽略、恢复和打断策略，以及这些策略如何影响自然度、控制感、参与度和系统人格。
3. **语音 Agent 与可视化系统**分别开始支持多步工具调用或语音控制 dashboard，但前者通常没有持久的可视分析状态，后者通常还是 push-to-talk 或轮次式交互。

本次检索中，**没有发现一个已发表的、与 VerbalVis 足够接近的系统，同时满足以下条件**：

* 系统说话时持续监听；
* 用户可在系统说话或执行分析期间修改分析意图；
* 系统不仅停止音频，还撤销或废弃过时的分析动作；
* 根据新目标进行分析级 replanning；
* 将语音、工具执行和可变 dashboard 状态重新同步。

最接近的工作是 **Full-Duplex-Bench-v3**：它已经把真实语音中的自我修正、参数更新和多步 API 调用纳入评估；但它是语音工具调用 benchmark，不涉及 visual analytics、dashboard consistency，也没有系统评估“已经启动或已经提交的旧工具动作如何取消或回滚”。([arXiv][1])

---

## 二、首先需要严格区分的四个概念

| 类型               | 系统行为                                     | 是否等于 VerbalVis 所需的 full-duplex |

| ---------------- | ---------------------------------------- | ------------------------------ |

| **Half-duplex**  | 用户说完后系统才处理并回答；系统说话时通常不接受有效输入             | 否                              |

| **Push-to-talk** | 用户按住按钮发送语音；可以使用流式 ASR，但交互权仍由按钮和轮次控制      | 否                              |

| **Streaming**    | ASR、LLM 或 TTS 增量运行；但系统仍可能在说话时关闭输入或等待完整轮次 | 不一定                            |

| **Full-duplex**  | 输入和输出在时间上并行；用户当前语音能够因果性地改变系统正在产生的输出或对话状态 | 是，但仍不自动意味着任务级取消                |

因此，**streaming 并不等于 full-duplex**。SyncLLM 等系统使用固定时间片交错处理输入和输出，可以产生类似重叠对话的效果；但近期综述指出，在单个时间片内，当前用户音频不能立即影响正在输出的内容，因此更接近“apparent full-duplex”，而不是完全连续的因果全双工。([ACL Anthology][2])

对 VerbalVis 更重要的另一条边界是：

> **停止说话不等于取消任务。**

可以将 interruption handling 分为五层：

| 层级                                       | 中断后的行为                        |

| ---------------------------------------- | ----------------------------- |

| L0：Playback stop                         | 停止播放尚未播出的音频                   |

| L1：Generation cancel                     | 取消当前语言或语音 response            |

| L2：Pending-action invalidation           | 阻止尚未执行的旧工具调用                  |

| L3：Running/committed-action cancellation | 取消执行中的查询，或回滚已经写入的界面状态         |

| L4：Analytical replanning                 | 根据修订后的目标重新规划分析步骤并同步 dashboard |

当前语音研究主要集中在 **L0–L1**。FDB-v3 开始涉及在 API 调用前根据用户自我修正更新参数和内部状态，但仍没有完整解决具有外部副作用的 L3–L4 问题。

---

# 三、Foundational Papers

## 3.1 Turn-taking 与增量处理基础

### Sacks, Schegloff, and Jefferson, 1974

该工作建立了经典的 conversation-analysis turn-taking 框架，包括 turn construction、transition relevance place、speaker selection、overlap 和 repair。它不是计算系统，但构成后续话轮预测、打断和 backchannel 研究的理论基础。

### Heins et al., 1997 — *Turn-taking as a Design Principle for Barge-in*

这是早期将 barge-in 作为语音界面设计原则进行系统讨论的工作。其重点是让用户不必等待系统完整播报结束即可夺取话轮，但仍然属于传统模块化 spoken-language system，不涉及正在执行的领域任务。([Springer][3])

### Schlangen and Skantze, 2011 — *A General, Abstract Model of Incremental Dialogue Processing*

该工作提出 incremental units、增量模块通信以及 add/revoke 操作。尤其值得 VerbalVis 引用的是：模型允许输入修订后撤销依赖于旧输入生成的中间结果，并回到先前有效状态。它在概念上是 **stale-result invalidation** 的早期架构基础，但论文讨论的是通用增量对话处理，而不是可视化工具和 dashboard 状态。([ACL Anthology][4])

### Skantze, 2017 与 Voice Activity Projection, 2022

Skantze 将 turn-taking 建模为连续的未来语音活动预测，而不只是“当前有没有声音”的二元 VAD。VAP 进一步通过自监督学习预测未来联合语音活动，可用于判断 turn shift、turn hold、backchannel opportunity 和 overlap。它们解决的是**什么时候说或让出话轮**，不负责理解用户正在修订哪个领域目标。([ACL Anthology][5])

### Turn-taking Surveys

Skantze 2021 是较完整的计算话轮综述。Castillo-López et al. 2025 更新了神经话轮预测、backchannel、多模态信号和数据集研究，并指出人类对话间隔平均约为 200 ms，而不少语音 Agent 仍存在约 700–1000 ms 的话轮间隔；该综述还发现 72% 的相关论文没有与既有方法进行充分比较，反映出 benchmark 不统一的问题。([kth.diva-portal.org][6])

---

# 四、Recent Full-Duplex Speech Models

符号说明：

* **A**：主要依据声学活动、音量、说话人或 VAD 信号。
* **S**：结合语言和上下文判断中断含义。
* **Implicit-S**：端到端模型可能学习了语义差异，但没有显式输出“backchannel / revision”类别。
* **Speech-only cancel**：只改变说话状态，没有证据表明取消领域任务。

| 工作                                                   | 模式与持续监听                                                                  | overlap / barge-in 理解                                         | 中断后取消什么                               | 工具或可变 UI           | 主要评价                                                                                               |

| ---------------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------- | ------------------------------------- | ------------------ | -------------------------------------------------------------------------------------------------- |

| **Duplex Conversation, KDD 2022**                    | 模块化 full-duplex；包含 user-state detection、backchannel selection 和 barge-in | A + 部分对话状态；能够区分若干用户状态                                         | 主要是话轮和系统语音行为                          | 无外部工具与 mutable UI  | 在线客服 A/B 测试；报告约 50% response-latency reduction ([ACM Digital Library][7])                          |

| **Full-duplex Speech Dialogue Scheme, NeurIPS 2024** | perception 和 motor 模块并行；LLM 通过控制 token 决定 start、wait 或 interrupt         | S；LLM 根据序列化上下文控制 neural FSM                                   | Speech/floor-control；无任务取消            | 无                  | 相比 LLM half-duplex 平均响应延迟降低三倍以上；超过一半交互在 500 ms 内响应；interruption precision 提升 8% ([NeurIPS 会议录][8]) |

| **SyncLLM, EMNLP 2024**                              | 160–240 ms 时间片交错输入输出；可模拟 overlap 和 backchannel                           | Implicit-S，但时间片内部不能即时响应新输入                                    | 下一时间片的生成内容                            | 无                  | dialogue meaningfulness、naturalness、模拟 Agent-Agent latency；不是领域任务评价 ([ACL Anthology][2])           |

| **Moshi, 2024**                                      | 真正并行建模用户与 Agent 两条音频流；无显式话轮边界                                            | Implicit-S；可学习 interruption、interjection、overlap              | 改变或停止语音 token 流；未定义工具生命周期             | 无                  | 理论延迟 160 ms，实际约 200 ms；语音质量与对话自然性 ([arXiv][9])                                                     |

| **LSLM, AAAI 2025**                                  | streaming speech encoder 与 speaking decoder 并行；明确 listen while speaking  | command-based 和 voice-based interruption；较偏 A/指令识别            | Speech generation / turn state        | 无                  | interruption detection、噪声鲁棒性、语音质量，不评价任务回滚 ([AAAI出版物][10])                                          |

| **SALMONN-omni, NeurIPS 2025**                       | 单一 standalone LLM 同时处理 environment stream 与 assistant stream             | 较强 S；明确评估 contextual barge-in、backchannel 和 echo cancellation | 生成 `<think>`、`<shift>` 等状态控制；仍主要是语音状态 | 无                  | turn-taking、backchannel、context-dependent barge-in、speech QA；相对既有开放模型提高至少 30% ([NeurIPS 会议录][11])  |

| **Semantic-Aware Interruption Detection, 2026**      | 不是完整语音 Agent，而是 interruption detector                                    | 明确 S；目标正是避免把 backchannel/noise 当成真实中断                         | 只输出 interruption decision             | 无                  | SID-Bench 与 Average Penalty Time；同时惩罚 false alarm 和迟响应，APT 约降低三倍 ([arXiv][12])                     |

| **MoshiRAG, 2026**                                   | Moshi 式 full-duplex + 异步 retrieval                                       | 保留 pause、barge-in、backchannel 能力；未专门评价 intent revision        | 可调整正在形成的回答，但没有报告取消 retrieval 或回滚外部状态  | 有外部知识检索，但不是可变工具环境  | factuality、交互性、异步检索延迟 ([arXiv][13])                                                                |

| **Full-Duplex-Bench-v3, 2026**                       | benchmark；评估多个实时语音 Agent                                                 | 同时考察 filler、pause、hesitation、false start 和 self-correction    | 要求在 API 调用前丢弃旧参数并更新内部状态；没有验证已提交动作回滚   | 多步 API chain；无可视界面 | Pass@1、参数正确性、turn-take、interruption、first-word/tool/task latency ([arXiv][14])                     |

## 关键判断

### 1. Acoustic interruption detection 与 semantic interruption understanding

传统 VAD 只能回答：

> “现在有没有人声？”

但无法回答：

> “这是‘嗯嗯’式 backchannel、环境噪声、重复系统最后一个词，还是用户正在修改目标？”

SALMONN-omni 和 Semantic-Aware Interruption Detection 开始处理这一层语义差异。后者尤其指出，过度敏感的 VAD 会将 backchannel 误判为中断，而过度谨慎的端到端模型又会产生过长延迟。([NeurIPS 会议录][11])

然而，即使能够识别“这是真实中断”，仍未回答：

> 该中断是补充信息、局部参数修正、目标转换，还是要求取消整个正在执行的计划？

这正是 VerbalVis 的 **analytical-intent revision** 层。

### 2. Turn-taking latency 与 task-level latency

现有论文经常报告：

* end-of-turn delay；
* first-token / first-word latency；
* interruption detection latency；
* speech stop latency；
* backchannel timing。

但 Agent 使用工具后，还应区分：

* tool-selection latency；
* tool-start latency；
* query-completion latency；
* dashboard-render latency；
* revision-to-consistent-state latency。

FDB-v3 已经把延迟拆成 first word、tool call 和 task completion。其结果也显示“更快说话”不一定意味着“更快完成任务”：例如某些 Agent 会先说 filler，再较晚调用工具。

### 3. Agent interruption 与 user barge-in 不是同一问题

不少 proactive-agent 研究中的 interruption 是：

> Agent 主动打断正在做其他事情的用户。

VerbalVis 的关键现象则是：

> 用户在 Agent 正在解释或执行分析时打断 Agent。

两者都涉及 timing 和礼貌，但后者还需要处理旧语音、旧计划和旧界面状态的失效。

---

# 五、HCI Interruption Studies

| 工作                                                              | 研究的中断形式                                          | 主要发现                                                                                           | 与 VerbalVis 的距离                                                                |

| --------------------------------------------------------------- | ------------------------------------------------ | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |

| **Heins et al., 1997**                                          | 用户在系统提示期间 barge-in                               | 将 barge-in 视为自然话轮设计要求，而非单纯 ASR 功能                                                              | 没有语义 revision 和任务状态 ([Springer][3])                                            |

| **Crook et al., 2012**                                          | 用户打断 embodied conversational agent               | 系统快速响应中断，并根据上下文生成 address + resumption；是早期超越“直接停音频”的工作                                         | 会修复对话叙事，但不会取消领域工具或改变外部状态 ([Springer][15])                                      |

| **Eliciting Spoken Interruptions, CUI 2021**                    | 人在执行任务时被另一人用语音打断；用于设计 proactive Agent            | 紧急条件下用户更早打断，并会根据被打断任务的节奏选择 timing；措辞和语调也随紧急程度变化                                                | 研究 Agent 应何时主动打断用户，不是用户修订 Agent 任务 ([arXiv][16])                               |

| **Can VUI Turn-Taking Entrain User Behaviours?, IndiaHCI 2022** | VUI 不允许重叠语音                                      | 严格禁止 overlap 会迫使用户适应机器的话轮节奏，并带来 turn-taking challenges                                         | 证明 half-duplex 会改变用户行为，但没有动态分析任务 ([ACM Digital Library][17])                   |

| **TalkTive, CHI 2022**                                          | Agent 在老年用户说话期间提供 reactive/proactive backchannel | 研究 246 段人际对话并开展 36 人研究；主动鼓励式 backchannel 比简单 reactive backchannel 更受欢迎                         | 支持 one-way overlap，但不是用户 barge-in，也不修改 Agent 计划 ([arXiv][18])                  |

| **Let Me Finish First, IVA 2024**                               | 用户打断正在说话的社交 Agent                                | 比较 Ignore、Accept、Acknowledge 三种策略；“先承认、但坚持说完再回答”显著更不受欢迎，且被认为更不 agreeable、更不 emotionally stable | 说明 interruption policy 影响人格和控制感；Accept 策略仍会恢复原话题，而不是重新规划任务 ([Diva Portal][19]) |

| **Older Adults Barge-in Agent, CHI 2025**                       | LLM Agent 支持用户打断和系统 backchannel                  | 通过老年用户研究发现，支持 barge-in 的 Agent 在自然度、参与感和流畅度方面优于不支持打断的版本                                        | 非分析任务；没有工具取消、状态回滚或 dashboard synchronization ([ACM Digital Library][20])       |

## 对 VerbalVis 最重要的 HCI 启示

**让用户能够发出声音，不等于让用户获得控制权。**

例如，*Let Me Finish First* 中的 Acknowledge 策略虽然检测到了中断、暂停了语音并口头承认用户，却仍坚持先完成自己的旧话轮。用户因此对 Agent 的评价反而更差。([Diva Portal][19])

映射到 visual analytics：

* 仅停止 TTS，但旧查询继续执行，属于表面控制；
* 接收新语音，但旧图稍后仍覆盖 dashboard，属于状态冲突；
* 口头说“好的，改看评分”，但后台仍在计算销售趋势，属于 analytical inconsistency。

因此，VerbalVis 的用户控制应通过**旧动作是否实际失效**来测量，而不能只测“系统有没有停止说话”。

---

# 六、Systems Closest to VerbalVis

## 6.1 Full-Duplex-Bench-v3：最接近“全双工 + 工具”

FDB-v3 包含真实人类录音、五种 disfluency、多步骤 API chain 和四类任务领域。部分场景要求 Agent 处理：

> “订去纽约的航班……等一下，改成波士顿。”

Agent 应在发出 booking call 前丢弃纽约参数并更新为波士顿。该工作明确将这类问题描述为 **self-correction and state rollback**。

但它与 VerbalVis 仍有三点本质差异：

1. 修正主要发生在用户自己的一个未完成 utterance 内，而不一定发生在 Agent 说话或工具执行期间。
2. 主要检查最终 API 调用参数是否正确，没有 persistent dashboard state。
3. 没有评价已经开始执行或已经更新界面的旧动作如何取消、补偿或回滚。

其结果也证明这不是已解决的问题：表现最好的 GPT-Realtime 在 self-correction 类别上的 Pass@1 为 0.588，仍有超过 40% 场景失败；困难多步场景的准确率也明显下降。

## 6.2 MoshiRAG：最接近“全双工 + 外部计算”

MoshiRAG 在 full-duplex 对话继续进行的同时异步检索外部知识，使系统可先开始自然响应，再将检索结果融入后续内容。([arXiv][13])

但 retrieval 通常是：

* 只读；
* 无持久副作用；
* 不改变 dashboard；
* 不需要撤销多个相互依赖的可视分析动作。

所以它解决的是 **asynchronous knowledge augmentation**，不是 **interruptible analytical execution**。

## 6.3 Hey Dashboard!/DIANA：最接近“语音 + Dashboard”

CHI 2026 的 DIANA 将语音、文字和鼠标指向与 Power BI dashboard 结合，能够根据用户问题解释并高亮 dashboard 元素。它是本次检索中最接近 VerbalVis 应用界面的工作。([arXiv][21])

但是其界面明确采用 **push-to-talk**，研究重点是 dashboard onboarding 和多模态选择，不是系统说话期间的 barge-in。它没有研究旧解释或旧 dashboard 操作的失效问题。

## 6.4 由此形成的三角空白

| 研究方向                  |    Full-duplex |            多步工具 | Mutable dashboard |     中断触发旧动作失效 |

| --------------------- | -------------: | --------------: | ----------------: | ------------: |

| Moshi / SALMONN-omni  |              ✓ |               — |                 — |          仅语音层 |

| FDB-v3                |    ✓/benchmark |               ✓ |                 — | 部分，主要为调用前参数修正 |

| DIANA / Hey Dashboard | —，push-to-talk | 部分 dashboard 操作 |                 ✓ |             — |

| **VerbalVis**         |              ✓ |               ✓ |                 ✓ |      **核心机制** |

---

# 七、对十个检索问题的总体回答

1. **Half-duplex、streaming 和 full-duplex 经常被混用。**真正关键的是系统说话期间是否继续处理输入，以及输入能否立即改变当前输出。
2. **User barge-in、agent interruption、backchannel 和 noise 是不同事件。**传统 VAD 很难区分；近期 semantic interruption detection 才开始正面解决。
3. **声学检测已经较成熟，语义检测仍是新问题。**尤其是 backchannel 与 intent revision 的区分。
4. **多数工作只截断音频或切换 speaking state。**很少研究 underlying computational task。
5. **turn-taking latency 不能代表 task-level latency。**低 first-word latency 甚至可能掩盖较迟的工具调用和完成时间。
6. **Moshi、LSLM、SALMONN-omni 等确实可以边说边听。**一些仅使用时间片交替的系统属于近似或 pseudo-simultaneous full-duplex。
7. **SALMONN-omni 和 semantic-aware detector 开始区分 contextual barge-in 与 backchannel。**但尚未进一步判断“分析目标如何变化”。
8. **连接外部工具的直接证据主要来自 FDB-v3、VoiceAgentBench 和 MoshiRAG。**连接 mutable visual interface 的工作主要是 DIANA，但它不是 full-duplex。
9. **多数 interruption 只导致停止或让出话轮。**显式 analytical replanning 几乎没有被研究。
10. **评价指标仍被分割为两组：**语音工作测延迟、自然度和 interruption precision；Agent 工作测工具正确性；HCI 工作测控制感、参与度和人格。尚缺跨层指标。

---

# 八、建议 VerbalVis 采用的评价指标

为了证明贡献不只是“语音停得快”，建议至少分四层报告：

### Conversational coordination

* Barge-in detection latency
* Speech cessation latency
* False interruption rate
* Backchannel false-positive rate
* Overlap duration

### Computational invalidation

* Stale response cancellation rate
* Stale tool-call prevention rate
* In-flight action cancellation success
* Committed-state rollback success
* Late stale-result leakage rate

其中最后一项尤其重要：旧查询虽然已被判为失效，但结果仍晚到并覆盖 dashboard，应被视为 failure。

### Analytical replanning

* Revised-intent interpretation accuracy
* Replanning latency
* Revised task completion
* Number of obsolete steps executed
* Analysis coverage after revision

### Human experience

* Perceived control
* Conversational naturalness
* Interruption confidence
* Recovery clarity
* Trust in dashboard consistency
* Cognitive effort
* Preference over turn-based baseline

---

# 九、可直接用于 Related Work 的 Gap Statement

前述证据显示，现有工作分别覆盖了 full-duplex turn coordination、语义中断检测、多步语音工具调用和语音 dashboard interaction，但尚未将四者结合。([arXiv][12])

Full-duplex conversational AI has primarily investigated when an agent should listen, speak, stop, backchannel, or yield the floor. Recent systems can process overlapping speech and, increasingly, distinguish meaningful interruptions from acoustic activity or conversational backchannels. However, interruption handling remains largely utterance-level: stopping or revising a spoken response does not necessarily invalidate the computation or interface actions initiated under the superseded intent. Work on full-duplex tool-using agents has only recently begun to examine spoken self-corrections and multi-step API execution, while voice-enabled visualization systems remain predominantly turn-based or push-to-talk. Consequently, little is known about the domain-level consequences of interruption during visual analysis, including how to invalidate stale analytical actions, replan an ongoing analysis, and synchronize speech, tool execution, and dashboard state after a user revises their intent.

更短的一句定位可以写成：

> **Prior work makes spoken interaction interruptible; VerbalVis makes the ongoing visual analysis interruptible.**

---

# 十、BibTeX

已整理 **22 条 BibTeX**，包括：

* turn-taking 与 incremental dialogue 基础文献；
* Duplex Conversation、SyncLLM、Moshi、LSLM、SALMONN-omni；
* semantic interruption、MoshiRAG、FDB-v3；
* CHI/CUI/IVA interruption 与 older-adult studies；
* CHI 2026 Hey Dashboard!/DIANA。

同行评审版本优先使用正式 venue 和 DOI；截至检索日期尚未确认正式出版版本的论文以 `@misc` 和 arXiv 编号标记。

[下载 VerbalVis Part 3 verified BibTeX](sandbox:/mnt/data/verbalvis_part3_full_duplex_verified.bib)

[1]: https://arxiv.org/pdf/2604.04847
[2]: https://aclanthology.org/2024.emnlp-main.1192/
[3]: https://link.springer.com/article/10.1007/BF02208827?utm_source=chatgpt.com
[4]: https://aclanthology.org/2011.dnd-2.11/?utm_source=chatgpt.com
[5]: https://aclanthology.org/W17-5527/?utm_source=chatgpt.com
[6]: https://kth.diva-portal.org/smash/record.jsf?pid=diva2%3A1527596&utm_source=chatgpt.com
[7]: https://dl.acm.org/doi/10.1145/3534678.3539209?utm_source=chatgpt.com
[8]: https://proceedings.neurips.cc/paper_files/paper/2024/hash/180d4373aca26bd86bf45fc50d1a709f-Abstract-Conference.html
[9]: https://arxiv.org/abs/2410.00037
[10][10]: https://ojs.aaai.org/index.php/AAAI/article/view/34665 "

    Language Model Can Listen While Speaking

    \| Proceedings of the AAAI Conference on Artificial Intelligence

    "

[11]: https://proceedings.neurips.cc/paper_files/paper/2025/hash/233aee920dab065709145371b5900b8f-Abstract-Conference.html
[12]: https://arxiv.org/abs/2603.24144?utm_source=chatgpt.com
[13]: https://arxiv.org/abs/2604.12928?utm_source=chatgpt.com
[14]: https://arxiv.org/abs/2604.04847?utm_source=chatgpt.com
[15]: https://link.springer.com/article/10.1007/s12193-012-0090-z?utm_source=chatgpt.com
[16]: https://arxiv.org/abs/2106.02077?utm_source=chatgpt.com
[17]: https://dl.acm.org/doi/10.1145/3570211.3570215?utm_source=chatgpt.com
[18]: https://arxiv.org/abs/2202.08216?utm_source=chatgpt.com
[19]: https://www.diva-portal.org/smash/get/diva2%3A1913220/FULLTEXT01.pdf
[20]: https://dl.acm.org/doi/full/10.1145/3706598.3714228?utm_source=chatgpt.com
[21]: https://arxiv.org/abs/2510.12386?utm_source=chatgpt.com
# Prompt 4：Sensemaking 检索结果

## 1. 核心结论

这组文献为 VerbalVis 提供了较强的**理论合理性**，但并没有提供一个现成的三分类体系。

现有研究基本形成了三层递进关系：

1. **Sensemaking 理论**已经把分析描述为迭代过程：分析者不断搜索证据、形成结构、检验解释，并在证据不匹配时修改问题框架、假设或知识结构。
2. **Analytical provenance 系统**能够记录、回放、比较、分支或恢复分析路径，但大多数系统处理的是已发生的交互历史，而不是把用户正在表达的意图修订作为即时控制信号。
3. **LLM-supported sensemaking 系统**开始支持多轮分析、分支、层级组织和 insight navigation，但交互通常仍是文本式、轮次式的；本次检索没有发现系统研究“用户在 AI 正在说话或执行分析时打断，并使旧分析计划与视觉操作立即失效”的完整问题。

因此，VerbalVis 的 **Goal Shift、Hypothesis Correction、Scope Narrowing** 最适合定位为：

> **A theory-informed coding framework and design-oriented conceptual lens for characterizing interruption-induced analytical intent revision.**

不建议直接称为 established taxonomy。它们不是系统运行时的 dispatch classes，而是论文层面用于解释和编码 interruption episodes 的分析类别。

---

# 2. 六个研究板块

## A. Foundational models of sensemaking and information foraging

### Russell et al.：sensemaking 的成本结构

Russell 等将 sensemaking 定义为：寻找一种合适的表征，并把数据编码到这种表征中，以回答特定任务问题。分析者会在信息检索、表征构建和数据编码的成本之间进行权衡；当当前表征无法容纳数据时，会发生 representation shift。因此，sensemaking 不是固定流水线，而是围绕表征不断调整的过程。([ACM Digital Library][1])

这一理论对 VerbalVis 的价值在于：用户打断不仅可能改变查询参数，也可能表明当前分析表征的成本过高或不再适合当前问题，需要切换分析框架。

### Pirolli and Card：foraging loop 与 sensemaking loop

Pirolli 和 Card 将分析过程划分为：

* information foraging loop：搜索、筛选、阅读和提取信息；
* sensemaking loop：建立 schema、形成假设、组织证据并构建结论。

两个循环之间存在反复移动。新证据既可能支持当前理论，也可能反驳它，还可能触发新假设和新的信息搜索。([andymatuschak.org][2])

这是 **Hypothesis Correction** 最直接的理论基础之一：新证据不仅增加信息，还可能使当前解释失效。

### Klein et al.：Data–Frame Theory

Data–Frame Theory 将 sensemaking 描述为数据与 frame 相互适配的过程。Frame 决定哪些数据值得关注、如何解释数据；数据反过来可以：

* elaborating a frame；
* questioning a frame；
* comparing alternative frames；
* reframing；
* abandoning a frame。

当新数据无法被现有 frame 解释时，分析者可能修改甚至替换 frame。([Taylor & Francis][3])

这里的 **reframing** 与 Goal Shift 部分重叠，而 frame elaboration、questioning 和 replacement 与 Hypothesis Correction 部分重叠。

### Zhang and Soergel：conceptual change

Zhang 和 Soergel 将 sensemaking 扩展为包含过程、知识表征与认知机制的迭代模型。他们把知识结构变化划分为：

* **Accretion**：向原有结构增加信息；
* **Tuning**：弱修订，包括约束 schema 的适用范围、调整概念的重要性或提高结构与数据的匹配程度；
* **Restructuring**：当新信息与原有知识冲突时，对知识结构进行根本修改或创建新结构。([SUNY Research Connect][4])

其中，原文对 tuning 的描述明确包含“constraining the extent of a schema’s applicability”，这是 **Scope Narrowing** 最强的相邻理论先例；restructuring 则与 Goal Shift 和较强的 Hypothesis Correction 重叠。([ResearchGate][5])

其后续用户研究通过 think-aloud、屏幕记录、笔记、概念图和最终报告观察到，sensemaking 由多次 search–sensemaking iterations 构成，而不是简化的 waterfall。([Sage Journals][6])

---

## B. Exploratory visual analysis and iterative hypothesis formation

### Sacha et al.：Knowledge Generation Model

Sacha 等人的模型明确区分 exploration、verification 和 knowledge generation loops。分析者通过可视化发现证据和模式，再用这些证据验证或证伪假设，并根据结果继续探索。([kops.uni-konstanz.de][7])

它支持 VerbalVis 的基本论点：visual analysis 的输出不只是“答案”，而是会反过来改变下一步问题和假设。

### Battle and Heer：EVA 中目标逐渐演化

Battle 和 Heer 的综述与 Tableau provenance 研究指出，exploratory visual analysis 往往没有从一开始就确定的目标。分析者可能从模糊问题开始，随着探索逐渐 refine、sharpen 或 focus 分析目标。([homes.cs.washington.edu][8])

它为两个类别提供了直接支撑：

* **Goal Shift**：分析目标在探索过程中可能变化；
* **Scope Narrowing**：模糊、宽泛的问题逐渐变成聚焦的分析问题。

但该文并未把两者定义成一个正式 taxonomy。

### EVM：显式检查 provisional interpretations

EVM 允许用户把暂时性的解释表示为统计模型，并把模型预测与实际数据进行可视比较。用户可以表达多个可能解释，发现模型与观察不匹配，并调整变量、关系或模型结构。研究使用 12 名实际数据工作者的 think-aloud 和访谈，比较有无 model checking 时的分析行为。([UW Interactive Data Lab][9])

EVM 是 **Hypothesis Correction** 的直接系统先例之一，因为它：

* 允许用户显式表达 provisional interpretation；
* 支持检查、否定和修改解释；
* 不只是记录历史，而是主动支持 revision。

但 revision 仍发生在用户完成一次操作之后，而不是在系统正在生成或执行操作时通过 spoken interruption 完成。

### Davidson et al.：strategy evolution

Davidson 等研究参与者在多次沉浸式分析 session 中，如何逐渐形成、调整和完善空间组织策略。高质量分析者通常较早建立有意义的组织，并随着获得新知识继续 refinement。研究以屏幕录像、分析路径、报告正确性和专业分析员评分来考察策略演化。([PubMed][10])

该研究直接支持 **strategy change**，但策略变化主要由纵向行为观察得到，并不是用户显式说出“我要改变策略”。

---

## C. Analytical provenance and interaction-history systems

### Gotz and Zhou：从低层交互推断语义活动

Gotz 和 Zhou 将 insight provenance 定义为产生 insight 的过程和推理依据的历史记录。他们把底层事件提升为具有语义意义的 actions，并按照 semantic intent 对分析活动分类。([Sage Journals][11])

这是从 interaction logs 推断分析意图的重要先例，但其主要目标是记录和解释分析，而不是让用户在活动尚未完成时修改它。

### Ragan et al.：provenance 的类型与用途

Ragan 等区分：

* data provenance；
* visualization provenance；
* interaction provenance；
* insight provenance；
* rationale provenance。

其中 insight provenance 可以包括假设、发现和结论的演化，rationale provenance 则包括分析目标、策略和决策依据。不过，目标与推理通常无法仅从鼠标或键盘操作可靠推断，因此经常需要 annotations、think-aloud 或 verbal expressions。([地缘政治杂志][12])

这对 VerbalVis 很重要：用户的 spoken interruption 是一种显式 rationale provenance，比仅通过 dashboard log 猜测目标变化更直接。

### SensePath：自动日志加 think-aloud

SensePath 将网页分析过程建模为 task、subtask、action 和 event，并联合使用浏览器日志、屏幕录像与 think-aloud transcription，帮助研究者分析 sensemaking 路径。评估表明它能够减少人工分析时间并帮助识别步骤和策略。([ACM Digital Library][13])

但是 SensePath 面向的是**事后研究者分析**，而不是在分析过程中支持用户修订当前计划。

### Xu et al.：interaction/provenance survey

Xu 等人的综述将 provenance 研究组织为 WHY、WHAT、HOW，并指出主要用途包括：

* 理解用户；
* 回放和复现；

  -报告与协作；
* model steering；
* adaptive systems。

综述同时指出，对高层目标和 reasoning 的可靠推断，以及真正自适应的分析系统，仍是开放问题。([Wiley在线图书馆][14])

### ProvenanceLens：把历史作为当前分析属性

ProvenanceLens 将 interaction recency 和 frequency 直接作为可视属性，使用户在分析过程中查看哪些数据属性最近或频繁被访问，并据此过滤、排序或调整编码。16 人探索性研究发现，这种可视 provenance 可以促进 self-reflection，并暴露用户记忆与实际历史之间的差异。

它不再只是事后记录，而是允许历史影响新的分析方向。但它仍然没有处理正在进行的 AI action 的取消和替换。

---

## D. Branching, backtracking, and revision

### Derthick and Roth：branching history

该系统将用户操作保存为树形历史，使分析者能够：

* 返回旧状态；
* 从中间状态创建新分支；
* 在互相矛盾的分析情境之间切换；
* 比较不同 scenario；
* 执行 selective undo/redo。([ACM Digital Library][15])

这是 analysis branching 的直接先例，但分支基于已完成的 operations。

### Graphical Histories

Graphical Histories 自动记录可视分析状态和转换，支持回退、重访、交流与行为分析，并展示用户的 iterative exploration pattern。([ACM Digital Library][16])

它主要解决的是 state history 与 navigation，不表达用户为什么改变问题或假设。

### VisTrails

VisTrails 保存可视化 workflow 的不同版本、参数和依赖关系，使研究者能够比较不同 pipeline、回退旧版本并复现结果。它把科学探索建模为不断修改和比较 workflow 的过程。([ACM Digital Library][17])

其 revision 单位是 workflow version，而不是对话中的 analytical intent。

---

## E. LLM-supported sensemaking and conversational data analysis

### Sensecape

Sensecape 认为复杂信息任务是非线性的，而传统聊天界面通常是线性的。它使用 canvas、层级结构和 abstraction levels，使用户可以创建分支、组织主题并在 foraging 与 sensemaking 之间切换。用户研究发现参与者探索了更多主题，并形成了更有层次的知识结构。

Sensecape 是 Goal Shift 和 Scope Navigation 的重要相邻工作，但用户修改的是已生成的信息空间，不涉及 AI 正在输出时的打断。

### HINTs

HINTs 使用 hypergraph 表示文档集合，并把 LLM 同时用作 NLP solver 和 conversational agent。它强调可视化提供的 visual hints 能够弥补智能 agent 在 corpus sensemaking 中产生的新问题。评估包括两个 case studies 和比较用户研究。([arXiv][18])

它体现 human–AI sensemaking，但没有显式建模 analytical intent revision 或 mid-response interruption。

### InsightLens

InsightLens 针对 LLM 分析对话中 insight、代码、可视化和解释相互纠缠的问题，自动记录和组织 insight，并通过多视图支持导航。其 formative study 有 8 名分析者，用户研究有 12 名分析者；结果关注认知与手工组织负担、分析效率以及 insight/topic/attribute coverage。([arXiv][19])

InsightLens 支持：

* 查看 insight 之间的关系；
* 重新进入历史分析语境；
* 识别 conversational context transition；
* 保留或切换当前分析关注点。

但它主要管理已经产生的 conversational context，并不取消正在执行的旧分析。

### Data Has Entered the Chat / AI Threads

Hong 和 Crisan 分析了 50 名 data workers 与 GenAI agent 的 exploratory visual analytic conversations，并编码了 502 个 utterance–response pairs。他们提出了 analysis elaboration、refinement 和 explanation 等循环，并指出探索可能包含多个并行、反复的 foraging 与 sensemaking cycles。([ACM Digital Library][20])

AI Threads 允许用户：

* 从主对话创建 side thread；
* 在分支内修改 visualization；
* 将完成的分支结果带回主分析；
* redo 或 undo agent responses；
* 保留多个对话语境。

这是目前与 VerbalVis 的“分析方向变化”最接近的工作之一，但仍有本质区别：

* revision 发生在 agent 已返回结果之后；
* 用户通过 typed turn 或按钮操作创建分支；
* 没有研究 spoken overlap；
* 没有在 AI response 尚未结束时取消底层分析计划。

### Visualizing Tree-of-Analysis

2026 年的 Tree-of-Analysis 将 conversational VA 表示成一棵交互分析树：AI outputs 是节点，用户 queries 是边。其 formative study 发现 novice 用户容易忽略 analytical cues，而 experts 使用多类 query 组织 workflow。用户研究报告 task failure 减少、每轮 insight 增加，但每轮思考时间也有所增加。([pgl.jp][21])

它强化了“分析对话天然可以是树状而非线性”的论点，但仍属于 turn-based conversational history support。

### Human-centered AI and visualization frameworks

Elmqvist 和 Klokmose 把 AI 对可视化的能力分为 amplify、augment、empower 和 enhance，并映射到 view、explore、schematize、report 等 sensemaking 阶段。该框架强调人的 agency 和 AI 对分析过程的辅助作用，但没有细化用户如何在 agent 正在执行时改变其分析意图。([arXiv][22])

---

# 3. Evidence table

表中：

* **G** = Goal Shift
* **H** = Hypothesis Correction
* **S** = Scope Narrowing
* **St** = Strategy Switch
* “显式”指 think-aloud、annotation、用户陈述或分析模型；
* “推断”指从 interaction logs、状态转换或视频中推断。

| Work                           | Sensemaking 与过程                                     | 所支持的 revision construct | 变化如何被捕获                           | 系统对 revision 的支持                    | 运行中 revision / speech          | Evaluation                                                                             |

| ------------------------------ | --------------------------------------------------- | ----------------------- | --------------------------------- | ----------------------------------- | ------------------------------ | -------------------------------------------------------------------------------------- |

| Russell et al. 1993            | 搜索合适表征并将数据编码其中；迭代                                   | St；部分 G/H               | 理论模型                              | 解释 representation shift             | 不适用                            | 成本结构与 time–quality trade-off ([ACM Digital Library][1])                                |

| Pirolli & Card 2005            | foraging 与 sensemaking 双循环                          | G、H、St                  | cognitive task analysis           | 理论解释 evidence–hypothesis loop       | 不适用                            | 分析活动与 leverage points ([andymatuschak.org][2])                                         |

| Klein et al. 2007              | data 与 frame 相互适配、质疑和重构                             | G、H、St                  | 理论与案例                             | 支持 reframing 概念                     | 不适用                            | 理论解释，无系统实验 ([Taylor & Francis][3])                                                     |

| Zhang & Soergel 2014           | 搜索、结构构建、认知机制和概念变化的迭代模型                              | G、H、S、St                | 理论综合                              | 解释 accretion/tuning/restructuring   | 不适用                            | 文献综合与模型构建 ([SUNY Research Connect][4])                                                 |

| Zhang & Soergel 2016           | 多次 search–sensemaking iterations                    | H、S、St；部分 G             | think-aloud、屏幕、笔记、概念图、报告          | 描述 revision，未实时干预                   | 否；think-aloud 仅用于研究            | 15 人 qualitative study；过程 pattern 与概念变化 ([ResearchGate][5])                            |

| Sacha et al. 2014              | exploration、verification、knowledge generation loops | H、St                    | 分析交互和假设活动                         | 理论层面支持 verification/falsification   | 否                              | 模型综合与应用案例 ([kops.uni-konstanz.de][7])                                                  |

| Battle & Heer 2019             | EVA 目标从模糊到聚焦并反复调整                                   | G、S、St                  | Tableau provenance logs           | 主要记录和刻画路径                           | 否                              | 27 名 Tableau 用户；task performance、interaction patterns ([Wiley在线图书馆][23])               |

| EVM 2024                       | 显式表达并检查 provisional interpretations                 | **H 直接先例**；部分 S         | 用户显式指定模型，加 think-aloud            | 主动支持模型修订                            | 非运行中；无语音                       | 12 名 data workers；行为 motifs、qualitative comparison ([UW Interactive Data Lab][9])      |

| Davidson et al. 2023           | 多 session 中策略逐步演化                                   | **St 直接先例**             | 视频和空间组织行为推断                       | 支持用户组织，研究者事后分析                      | 否                              | 报告正确性、质量评分、策略相关性 ([PubMed][10])                                                        |

| Gotz & Zhou 2009               | insight 形成过程及其 rationale                            | G/H/St 的间接表示            | 从 events 提升为 semantic actions     | 记录 insight provenance               | 否                              | action taxonomy 与系统实例 ([Sage Journals][11])                                            |

| Ragan et al. 2016              | provenance 包括 interaction、insight 和 rationale       | G、H、St；部分 S             | logs 加 annotation/verbalization   | 组织与比较 provenance 用途                 | 未报告；verbalization 非交互通道        | 文献框架与设计空间 ([地缘政治杂志][12])                                                               |

| SensePath 2016                 | comprehension、meaning、insight 与后续 action            | St；可观察 G/H              | 浏览器日志、视频、think-aloud              | 事后转录、编码和回放                          | 否                              | 分析时间、可用性、策略识别 ([ACM Digital Library][13])                                              |

| Xu et al. 2020                 | interaction/provenance 的 WHY–WHAT–HOW               | 各类 revision 的观察基础       | logs、状态和高层 inference              | 总结 replay、steering、adaptation       | 少有运行中支持                        | survey taxonomy 与开放问题 ([WashU Research Profiles][24])                                  |

| ProvenanceLens 2025            | 用 recency/frequency 反思当前分析轨迹                        | S、St；部分 G               | 自动 interaction tracking           | 在分析中主动利用 provenance                 | 可在下一操作中修订；非 mid-action         | 16 人 study；回答准确度、信心、自我反思                                                               |

| Derthick & Roth 2001           | 多个探索 scenario 的树状历史                                 | G、S、St                  | 已完成 operation history             | branching、comparison、selective undo | 非运行中；无语音                       | 系统案例与功能分析 ([ACM Digital Library][15])                                                  |

| Graphical Histories 2008       | iterative exploration 的状态序列                         | G/S/St 的路径表现            | 自动状态日志                            | backtrack、revisit、communicate       | 非运行中                           | 行为图、历史导航和复现 ([ACM Digital Library][16])                                                |

| VisTrails 2006                 | workflow 版本不断分化和比较                                  | H、S、St                  | workflow provenance               | versioning、comparison、reproduction  | 非运行中                           | 科学 workflow 案例 ([ACM Digital Library][17])                                             |

| Sensecape 2023                 | 非线性、多层 abstraction 的 LLM sensemaking                | G、S、St                  | 用户显式创建和组织主题                       | branch、prune、navigate abstraction   | turn-based text；无 interruption | within-subject；topic breadth、revisit、hierarchy                                         |

| HINTs 2025                     | hypergraph + LLM agent 的 corpus sensemaking         | G/S/St 的部分支持            | 用户 query 与可视 interaction          | agent guidance 与 visual hints       | 文本聊天；未报告中途取消                   | 两个 case studies、比较用户研究 ([arXiv][18])                                                   |

| InsightLens 2025               | 组织和导航 LLM 分析中的 insight context                      | G、S、St                  | 自动提取 insight 与 context transition | 主动记录、聚类和导航                          | turn-based；无语音                 | 8 人 formative、12 人 study；effort、efficiency、coverage ([arXiv][19])                      |

| Data Has Entered the Chat 2025 | 多个并行且反复的 conversational analysis loops              | **G/S/St 直接会话先例**；部分 H  | 显式 utterances 加编码                 | branch、refine、redo、undo             | 结果后 revision；无 spoken overlap  | 50 人、502 utterance–response pairs、状态转移模型                                               |

| Tree-of-Analysis 2026          | 用树结构外化多轮 CVA journey                                | G、S、St                  | queries 与 AI outputs              | 可视化 branch 与 analytical cues        | turn-based；无 interruption      | formative N=12、study N=12、3 experts；failure、insights/turn、thinking time ([pgl.jp][21]) |

| Elmqvist & Klokmose 2025       | AI 能力映射到 view–explore–schematize–report             | 支持总体 human–AI alignment | 概念框架                              | 设计 agenda，而非具体 revision mechanism   | 未涉及                            | literature/design-space analysis ([IEEE Computer Society][25])                         |

---

# 4. 三个 VerbalVis 类别的概念有效性

## 4.1 Goal Shift

### 建议定义

> **Goal Shift occurs when an interruption changes the analyst’s primary analytical objective, question, or task frame, such that continuing the current analytical plan would no longer serve the revised objective.**

### 直接或部分先例

* Battle and Heer：analysis goals 从模糊问题逐渐演化；
* Klein et al.：reframing 或 replacement of the current frame；
* Pirolli and Card：新证据触发新 hypothesis 和新的 search；
* Data Has Entered the Chat：新问题可能离开当前 context 并形成新的 conversation branch；
* Zhang and Soergel：restructuring 或切换 task/search direction。([Wiley在线图书馆][23])

### 术语差异

相关文献更常使用：

* goal evolution；
* task reformulation；
* reframing；
* context shift；
* topic shift；
* analysis branch；
* strategy change。

因此，Goal Shift 是合理的论文术语，但不是现有公认 taxonomy 中的固定 label。

---

## 4.2 Hypothesis Correction

### 建议定义

> **Hypothesis Correction occurs when an interruption revises, rejects, qualifies, or replaces an interpretation, expectation, or explanatory hypothesis while retaining substantial continuity with the current analytical problem.**

### 直接先例

* Pirolli and Card：证据支持或反驳 theory；
* Sacha et al.：hypothesis verification 和 falsification；
* EVM：显式检查 provisional interpretations 并修改模型；
* Klein et al.：questioning、elaborating 或 replacing a frame；
* Zhang and Soergel：tuning 和 restructuring；
* Ragan et al.：hypotheses 属于 insight provenance。

### 术语差异

相关概念包括：

* hypothesis revision；
* theory disconfirmation；
* model checking；
* belief revision；
* interpretation refinement；
* frame questioning；
* tuning；
* restructuring。

三个类别中，**Hypothesis Correction 的理论支撑最直接**。

---

## 4.3 Scope Narrowing

### 建议定义

> **Scope Narrowing occurs when an interruption preserves the higher-level analytical objective but constrains the population, time period, variables, categories, geographic region, comparison set, or level of detail under consideration.**

### 直接或部分先例

* Zhang and Soergel 的 tuning 明确包括约束 schema 的适用范围；
* Battle and Heer 描述分析目标从宽泛、模糊逐渐变得 focused；
* Pirolli and Card 的 filtering 和 focused search；
* Sensecape 的 semantic dive、subtopic organization 和 abstraction navigation；
* provenance 与 history systems 中的 filter、drill-down 和 subset exploration。([ResearchGate][5])

### 关键限制

Scope Narrowing 是**有理论依据的操作性类别**，但不是广泛使用的标准术语。文献更常使用：

* focused search；
* constraint refinement；
* specification；
* filtering；
* drill-down；
* subset selection；
* narrowing the applicability of a schema。

此外，只使用 Narrowing 会产生不对称性：真实分析中也可能出现 scope broadening。

更严格的层级可以写成：

```text

Scope Revision

├── Scope Narrowing

├── Scope Broadening

└── Scope Substitution

```

如果当前研究案例只关注 narrowing，则应明确说明：

> We focus on scope narrowing because it was the dominant scope-revision form observed or instantiated in our interruption scenarios, rather than claiming that all scope revisions are narrowing operations.

---

# 5. Taxonomy、framework、coding scheme 还是 conceptual lens？

## 不建议：Established taxonomy

“Taxonomy”通常暗示：

* 类别具有较强完备性；
* 类别之间能够清晰区分；
* 分类规则经过系统性数据编码或验证；
* 不同编码者能够稳定复现；
* 所有 relevant cases 基本都能被覆盖。

目前三个类别存在明显交叠：

* “Forget sales; focus on low reviews in São Paulo”同时包含 Goal Shift 和 Scope Narrowing；
* “It may not be price; only examine delayed deliveries”同时包含 Hypothesis Correction 和 Scope Narrowing；
* 较强的 hypothesis correction 可能同时构成 reframing，因此也可能被编码为 Goal Shift。

所以，目前不能无条件宣称它们是互斥且穷尽的 taxonomy。

## 最推荐：Theory-informed coding framework

论文中可使用：

> **We use three theory-informed analytical categories—Goal Shift, Hypothesis Correction, and Scope Narrowing—to characterize how users revise analytical intent through interruptions. These categories serve as a paper-level coding framework and design-oriented conceptual lens rather than runtime intent classes or an exhaustive taxonomy of analytical change.**

该定位具有四个优势：

1. 承认类别受到 sensemaking、reframing、hypothesis testing 和 conceptual change 理论支持；
2. 不声称这些 labels 已经由前人正式建立；
3. 允许一个 interruption episode 使用多个 code；
4. 明确与系统实现解耦——系统无需先把 utterance 分类成三类才执行工具。

---

# 6. 建议编码规则

分析单位建议设为：

> **An interruption episode consisting of the pre-interruption analytical state, the interrupted system response or action, the user’s interrupting utterance, and the resulting analytical transition.**

### Goal Shift

当以下至少一项变化时编码：

* primary analytical question；
* task objective；
* target phenomenon；
* decision criterion；
* analysis frame。

仅改变筛选条件不应自动编码为 Goal Shift。

### Hypothesis Correction

需要用户显式或可可靠识别地：

* 否定先前解释；
* 修正因果或关联判断；
* 替换假设；
* 降低或提高对某个解释的确信；
* 指出当前 explanation/model 不匹配证据。

单纯提出新问题不应自动编码为 Hypothesis Correction。

### Scope Narrowing

需要：

* 保留原有高层问题；
* 同时缩小 population、time、region、attributes、categories、comparison set 或 granularity。

### 多标签策略

推荐记录：

```text

Primary revision type

Secondary revision type(s)

Revised entities or constraints

Invalidated analytical action

Resulting dashboard transition

```

统计图需要互斥类别时，可编码 dominant revision；质性分析中则应保留 secondary codes，并报告双人编码、分歧讨论和 Cohen’s κ 或 Krippendorff’s α。

---

# 7. 可借鉴的 evaluation measures

## Exploration breadth

已有工作常使用：

* unique attributes explored；
* unique topics；
* unique charts/views；
* number of branches；
* data-attribute coverage；
* revisits to earlier topics；
* breadth versus depth；
* analysis transitions。

Sensecape、InsightLens 和 Tree-of-Analysis 都提供了相邻测量思路。([Sangho Suh][26])

## Insight and hypothesis quality

可以使用：

* number of insights；
* insight correctness；
* insight depth or complexity；
* novelty；
* hypothesis specificity；
* evidence support；
* professional analyst report ratings；
* whether a hypothesis was retained, revised or rejected。

Davidson 等使用了报告正确性和专业评分，EVM 使用 think-aloud 和行为 motifs 考察 provisional interpretation 的变化。([PubMed][10])

## Strategy evolution

可编码：

* transitions between exploration and verification；
* strategy switching frequency；
* search–sensemaking loop count；
* branching factor；
* backtracking frequency；
* path entropy；
* repeated or redundant operations；
* time to converge on a stable frame。

## Provenance usefulness

常见指标包括：

* recall accuracy；
* analysis reconstruction time；
* confidence in recalling past activity；
* time saved during qualitative coding；
* successful undo/backtracking；
* ability to explain why an insight was reached；
* ability to resume an earlier branch。

SensePath 和 ProvenanceLens 分别提供了事后分析效率与分析历史自我反思的测量先例。([ACM Digital Library][13])

## VerbalVis 需要增加的专属指标

现有 sensemaking 指标不足以衡量 full-duplex revision，因此建议补充：

* **Interruption-to-speech-stop latency**
* **Interruption-to-stale-plan invalidation latency**
* **Stale tool-call execution rate**
* **Revision interpretation accuracy**
* **Dashboard convergence time**
* **Revision recovery success**
* **Need for repeated correction**
* **Mismatch between revised utterance and final visual state**
* **Exploration breadth after interruption**
* **Analytical continuity after interruption**

这里尤其要区分：

1. AI 停止播放旧语音；
2. AI 取消旧 response；
3. 后端阻止旧 tool call；
4. dashboard 不再应用旧结果；
5. 新分析目标被正确执行。

仅测量“语音停止得快”不能证明 analytical intent revision 被正确处理。

---

# 8. 最终 gap statement

推荐保留你给出的核心表述，并稍作学术化扩展：

> **Sensemaking research explains how analysts iteratively revise frames, hypotheses, knowledge structures, and strategies as new evidence emerges. Analytical-provenance and history systems can record, replay, branch, and compare evolving analysis trajectories, while recent LLM-supported interfaces help users organize and navigate nonlinear conversational analyses. However, these lines of work seldom examine how an evolving analytical intention, expressed through a mid-response spoken interruption, should immediately invalidate an AI agent’s stale response and analytical actions, replan the analysis, and synchronize the visual state with the user’s revised direction.**

更短版本：

> **Sensemaking and provenance research explains and records evolving analysis, but seldom studies how an evolving intention expressed through a mid-response interruption should immediately alter an AI-driven analytical plan and visual state.**

---

# 9. Verified BibTeX

以下条目的标题、作者、venue、卷期页码及 DOI 已通过正式出版页面、IEEE/ACM、出版社或作者页面交叉核对。([BibBase][27])

```bibtex

@inproceedings{russell1993cost,

  author    = {Russell, Daniel M. and Stefik, Mark J. and Pirolli, Peter and Card, Stuart K.},

  title     = {The Cost Structure of Sensemaking},

  booktitle = {Proceedings of the INTERCHI '93 Conference on Human Factors in Computing Systems},

  pages     = {269--276},

  year      = {1993},

  publisher = {Association for Computing Machinery},

  doi       = {10.1145/169059.169209}

}



@inproceedings{pirolli2005sensemaking,

  author       = {Pirolli, Peter and Card, Stuart},

  title        = {The Sensemaking Process and Leverage Points for Analyst Technology as Identified Through Cognitive Task Analysis},

  booktitle    = {Proceedings of the International Conference on Intelligence Analysis},

  volume       = {5},

  pages        = {2--4},

  year         = {2005},

  organization = {McLean, VA, USA}

}



@incollection{klein2007dataframe,

  author    = {Klein, Gary and Phillips, Jennifer K. and Rall, Erica L. and Peluso, Deborah A.},

  title     = {A Data--Frame Theory of Sensemaking},

  booktitle = {Expertise Out of Context: Proceedings of the Sixth International Conference on Naturalistic Decision Making},

  editor    = {Hoffman, Robert R.},

  pages     = {113--155},

  publisher = {Lawrence Erlbaum Associates},

  address   = {New York},

  year      = {2007},

  doi       = {10.4324/9780203810088-13}

}



@article{zhang2014comprehensive,

  author  = {Zhang, Pengyi and Soergel, Dagobert},

  title   = {Towards a Comprehensive Model of the Cognitive Process and Mechanisms of Individual Sensemaking},

  journal = {Journal of the Association for Information Science and Technology},

  volume  = {65},

  number  = {9},

  pages   = {1733--1756},

  year    = {2014},

  doi     = {10.1002/asi.23125}

}



@article{zhang2016process,

  author  = {Zhang, Pengyi and Soergel, Dagobert},

  title   = {Process Patterns and Conceptual Changes in Knowledge Representations During Information Seeking and Sensemaking: A Qualitative User Study},

  journal = {Journal of Information Science},

  volume  = {42},

  number  = {1},

  pages   = {59--78},

  year    = {2016},

  doi     = {10.1177/0165551515615834}

}



@article{sacha2014knowledge,

  author  = {Sacha, Dominik and Stoffel, Andreas and Stoffel, Florian and Kwon, Bum Chul and Ellis, Geoffrey and Keim, Daniel A.},

  title   = {Knowledge Generation Model for Visual Analytics},

  journal = {IEEE Transactions on Visualization and Computer Graphics},

  volume  = {20},

  number  = {12},

  pages   = {1604--1613},

  year    = {2014},

  doi     = {10.1109/TVCG.2014.2346481}

}



@article{battle2019characterizing,

  author  = {Battle, Leilani and Heer, Jeffrey},

  title   = {Characterizing Exploratory Visual Analysis: A Literature Review and Evaluation of Analytic Provenance in Tableau},

  journal = {Computer Graphics Forum},

  volume  = {38},

  number  = {3},

  pages   = {145--159},

  year    = {2019},

  doi     = {10.1111/cgf.13678}

}



@article{kale2024evm,

  author  = {Kale, Alex and Guo, Ziyang and Qiao, Xiao Li and Heer, Jeffrey and Hullman, Jessica},

  title   = {{EVM}: Incorporating Model Checking into Exploratory Visual Analysis},

  journal = {IEEE Transactions on Visualization and Computer Graphics},

  volume  = {30},

  number  = {1},

  pages   = {208--218},

  year    = {2024},

  doi     = {10.1109/TVCG.2023.3326516}

}



@article{davidson2023evolution,

  author  = {Davidson, Kylie and Lisle, Lee and Whitley, Kirsten and Bowman, Doug A. and North, Chris},

  title   = {Exploring the Evolution of Sensemaking Strategies in Immersive Space to Think},

  journal = {IEEE Transactions on Visualization and Computer Graphics},

  volume  = {29},

  number  = {12},

  pages   = {5294--5307},

  year    = {2023},

  doi     = {10.1109/TVCG.2022.3207357}

}



@article{gotz2009characterizing,

  author  = {Gotz, David and Zhou, Michelle X.},

  title   = {Characterizing Users' Visual Analytic Activity for Insight Provenance},

  journal = {Information Visualization},

  volume  = {8},

  number  = {1},

  pages   = {42--55},

  year    = {2009},

  doi     = {10.1057/ivs.2008.31}

}



@article{ragan2016characterizing,

  author  = {Ragan, Eric D. and Endert, Alex and Sanyal, Jibonananda and Chen, Jian},

  title   = {Characterizing Provenance in Visualization and Data Analysis: An Organizational Framework of Provenance Types and Purposes},

  journal = {IEEE Transactions on Visualization and Computer Graphics},

  volume  = {22},

  number  = {1},

  pages   = {31--40},

  year    = {2016},

  doi     = {10.1109/TVCG.2015.2467551}

}



@article{nguyen2016sensepath,

  author  = {Nguyen, Phong H. and Xu, Kai and Wheat, Ashley and Wong, B. L. William and Attfield, Simon and Fields, Bob},

  title   = {{SensePath}: Understanding the Sensemaking Process Through Analytic Provenance},

  journal = {IEEE Transactions on Visualization and Computer Graphics},

  volume  = {22},

  number  = {1},

  pages   = {41--50},

  year    = {2016},

  doi     = {10.1109/TVCG.2015.2467611}

}



@article{xu2020survey,

  author  = {Xu, Kai and Ottley, Alvitta and Walchshofer, Conny and Streit, Marc and Chang, Remco and Wenskovitch, John},

  title   = {Survey on the Analysis of User Interactions and Visualization Provenance},

  journal = {Computer Graphics Forum},

  volume  = {39},

  number  = {3},

  pages   = {757--783},

  year    = {2020},

  doi     = {10.1111/cgf.14035}

}



@article{narechania2025provenancelens,

  author  = {Narechania, Arpit and Guo, Shunan and Koh, Eunyee and Endert, Alex and Hoffswell, Jane},

  title   = {Utilizing Provenance as an Attribute for Visual Data Analysis: A Design Probe with {ProvenanceLens}},

  journal = {IEEE Transactions on Visualization and Computer Graphics},

  volume  = {31},

  number  = {10},

  pages   = {8452--8465},

  year    = {2025},

  doi     = {10.1109/TVCG.2025.3571708}

}



@article{derthick2001branching,

  author  = {Derthick, Mark and Roth, Steven F.},

  title   = {Enhancing Data Exploration with a Branching History of User Operations},

  journal = {Knowledge-Based Systems},

  volume  = {14},

  number  = {1--2},

  pages   = {65--74},

  year    = {2001},

  doi     = {10.1016/S0950-7051(00)00101-5}

}



@article{heer2008graphical,

  author  = {Heer, Jeffrey and Mackinlay, Jock and Stolte, Chris and Agrawala, Maneesh},

  title   = {Graphical Histories for Visualization: Supporting Analysis, Communication, and Evaluation},

  journal = {IEEE Transactions on Visualization and Computer Graphics},

  volume  = {14},

  number  = {6},

  pages   = {1189--1196},

  year    = {2008},

  doi     = {10.1109/TVCG.2008.137}

}



@inproceedings{callahan2006vistrails,

  author    = {Callahan, Steven P. and Freire, Juliana and Santos, Emanuele and Scheidegger, Carlos E. and Silva, Cl{\'a}udio T. and Vo, Huy T.},

  title     = {{VisTrails}: Visualization Meets Data Management},

  booktitle = {Proceedings of the 2006 ACM SIGMOD International Conference on Management of Data},

  pages     = {745--747},

  year      = {2006},

  publisher = {Association for Computing Machinery},

  doi       = {10.1145/1142473.1142574}

}



@inproceedings{suh2023sensecape,

  author    = {Suh, Sangho and Min, Bryan and Palani, Srishti and Xia, Haijun},

  title     = {{Sensecape}: Enabling Multilevel Exploration and Sensemaking with Large Language Models},

  booktitle = {Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology},

  articleno = {1},

  numpages  = {18},

  year      = {2023},

  publisher = {Association for Computing Machinery},

  doi       = {10.1145/3586183.3606756}

}



@article{lee2025hints,

  author  = {Lee, Sam Yu-Te and Ma, Kwan-Liu},

  title   = {{HINTs}: Sensemaking on Large Collections of Documents with Hypergraph Visualization and INTelligent Agents},

  journal = {IEEE Transactions on Visualization and Computer Graphics},

  volume  = {31},

  number  = {9},

  pages   = {5532--5546},

  year    = {2025},

  doi     = {10.1109/TVCG.2024.3459961}

}



@article{weng2025insightlens,

  author  = {Weng, Luoxuan and Wang, Xingbo and Lu, Junyu and Feng, Yingchaojie and Liu, Yihan and Feng, Haozhe and Huang, Danqing and Chen, Wei},

  title   = {{InsightLens}: Augmenting LLM-Powered Data Analysis with Interactive Insight Management and Navigation},

  journal = {IEEE Transactions on Visualization and Computer Graphics},

  volume  = {31},

  number  = {6},

  pages   = {3719--3732},

  year    = {2025},

  doi     = {10.1109/TVCG.2025.3567131}

}



@article{hong2025data,

  author  = {Hong, Matt-Heun and Crisan, Anamaria},

  title   = {Data Has Entered the Chat: How Data Workers Conduct Exploratory Visual Analytic Conversations with GenAI Agents},

  journal = {ACM Transactions on Interactive Intelligent Systems},

  volume  = {15},

  number  = {4},

  articleno = {21},

  pages   = {1--40},

  year    = {2025},

  doi     = {10.1145/3744750}

}



@inproceedings{qu2026tree,

  author    = {Qu, Feiyuan and Tang, Tan and Fu, Zeyang and Chen, Yan and Jia, Hanze and Gao, Junming and Nurdawulieti, Songela and Wu, Yingcai},

  title     = {Visualizing Tree-of-Analysis: Facilitating Conversational Visual Analytics for Novices},

  booktitle = {Proceedings of the 2026 CHI Conference on Human Factors in Computing Systems},

  articleno = {412},

  numpages  = {20},

  year      = {2026},

  publisher = {Association for Computing Machinery},

  doi       = {10.1145/3772318.3791690}

}



@article{elmqvist2025automating,

  author  = {Elmqvist, Niklas and Klokmose, Clemens Nylandsted},

  title   = {Automating the Path: An R\&D Agenda for Human-Centered AI and Visualization},

  journal = {IEEE Computer Graphics and Applications},

  volume  = {45},

  number  = {3},

  pages   = {73--81},

  year    = {2025},

  doi     = {10.1109/MCG.2025.3559374}

}

```

[1]: https://dl.acm.org/doi/10.1145/169059.169209?utm_source=chatgpt.com
[2]: https://andymatuschak.org/files/papers/Pirolli%2C%20Card%20-%202005%20-%20The%20sensemaking%20process%20and%20leverage%20points%20for%20analyst%20technology%20as.pdf?utm_source=chatgpt.com
[3]: https://www.taylorfrancis.com/chapters/edit/10.4324/9780203810088-13/data%E2%80%93frame-theory-sensemaking-gary-klein-jennifer-phillips-erica-rall-deborah-peluso?utm_source=chatgpt.com
[4]: https://researchconnect.suny.edu/en/publications/towards-a-comprehensive-model-of-the-cognitive-process-and-mechan/?utm_source=chatgpt.com
[5]: https://www.researchgate.net/publication/290391115_Process_patterns_and_conceptual_changes_in_knowledge_representations_during_information_seeking_and_sensemaking_A_qualitative_user_study
[6]: https://journals.sagepub.com/doi/10.1177/0165551515615834?utm_source=chatgpt.com
[7]: https://kops.uni-konstanz.de/handle/123456789/30001?utm_source=chatgpt.com
[8]: https://homes.cs.washington.edu/~leibatt/static/papers/battle_eurovis2019_cr_04_11_2019.pdf?utm_source=chatgpt.com
[9]: https://idl.cs.washington.edu/files/2024-EVM-TVCG.pdf
[10]: https://pubmed.ncbi.nlm.nih.gov/36112554/?utm_source=chatgpt.com
[11]: https://journals.sagepub.com/doi/10.1057/ivs.2008.31?utm_source=chatgpt.com
[12]: https://revistageo.com.br/revgeo/article/view/2143?utm_source=chatgpt.com
[13]: https://dl.acm.org/doi/abs/10.1109/TVCG.2015.2467611?utm_source=chatgpt.com
[14]: https://onlinelibrary.wiley.com/doi/abs/10.1111/cgf.14035?utm_source=chatgpt.com
[15]: https://dl.acm.org/doi/abs/10.1016/S0950-7051%2800%2900101-5?utm_source=chatgpt.com
[16]: https://dl.acm.org/doi/10.1109/TVCG.2008.137?utm_source=chatgpt.com
[17]: https://dl.acm.org/doi/10.1145/1142473.1142574?utm_source=chatgpt.com
[18]: https://arxiv.org/abs/2403.02752?utm_source=chatgpt.com
[19]: https://arxiv.org/abs/2404.01644?utm_source=chatgpt.com
[20]: https://dl.acm.org/doi/10.1145/3744750?utm_source=chatgpt.com
[21]: https://pgl.jp/conferences/chi2026/sessions/69dcad7b55a355001e07783a
[22]: https://arxiv.org/abs/2504.07529?utm_source=chatgpt.com
[23]: https://onlinelibrary.wiley.com/doi/abs/10.1111/cgf.13678?utm_source=chatgpt.com
[24]: https://profiles.wustl.edu/en/publications/survey-on-the-analysis-of-user-interactions-and-visualization-pro/?utm_source=chatgpt.com
[25]: https://www.computer.org/csdl/magazine/cg/2025/03/11086546/28xfzO7Bpq8?utm_source=chatgpt.com
[26]: https://sanghosuh.github.io/papers/sensecape_uist.pdf?utm_source=chatgpt.com

[27]: https://bibbase.org/network/publication/pirolli-card-thesensemakingprocessandleveragepointsforanalysttechnologyasidentifiedthroughcognitivetaskanalysis-2005?utm_source=chatgpt.com
