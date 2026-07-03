\section{形成性研究与设计需求}
\label{sec:formative-cn}

我们开展了一项轻量级形成性研究，以理解分析者如何在对话式可视分析中修订正在进行的分析，并据此提炼全双工可视分析系统的设计需求。本研究以系统设计为目的，而非验证性研究。我们并不试图建立穷尽性的探索行为分类，也不试图估计各类修订在更广泛人群中的出现频率。相反，我们首先基于既有理论确定探索过程中可能发生变化的分析对象，再考察这些变化如何出现在交互日志中，并通过复合案例和边界案例细化其操作定义。

\subsection{理论基础与研究问题}
\label{sec:formative-framing-cn}

探索性分析通常并不是执行一套预先完整规定且始终不变的计划。意义建构研究将分析描述为一个迭代过程：人们会围绕特定任务构建、检查并修订外部或内部表征
\cite{russell1993cost,pirolli2005sensemaking}。信息检索研究同样指出，随着新信息不断出现，用户的问题和查询会持续演化
\cite{bates1989berrypicking,vakkari2001changes}。在可视分析中，观察和洞见可能引出新的问题、改变后续探索方向，并将宽泛目标分解为更加聚焦的分析任务
\cite{sacha2014knowledge,battle2019characterizing,
lam2018bridging}。

既有研究也为暂定解释的变化提供了理论基础。数据--框架理论将意义建构描述为证据与解释框架之间的双向作用过程；当新的证据出现时，分析者可能扩展、质疑、比较或替换当前框架
\cite{klein2007dataframe,pontis2016influence}。科学推理研究进一步区分了假设空间中的搜索与实验或证据空间中的搜索
\cite{klahr1988dual}。可视分析模型也将假设生成、验证和证伪视为迭代知识生成的重要组成部分
\cite{sacha2014knowledge,shrinivasan2008supporting}。由于经过修订的解释仍然是暂定的，并不意味着它已经被证明为正确，因此我们采用
\emph{工作假设修订}，而不是“假设纠正”
\cite{chinn1993anomalous,thagard1989explanatory}。

第三类理论基础涉及渐进聚焦。信息觅食理论和交互式信息检索研究描述了宽泛的信息需求如何通过缩小搜索空间、重构查询以及选择更相关的信息区域而逐渐具体化
\cite{pirolli1999information,bates1989berrypicking,
vakkari2001changes}。可视化任务研究进一步区分了分析的目的、分析所针对的数据对象，以及实现该目的的交互方法
\cite{brehmer2013multilevel,lam2018bridging}。Voyager 等系统则通过分面浏览，将对数据属性和视觉属性的渐进式指定落实为具体交互机制
\cite{wongsuphasawat2016voyager}。

基于这些研究传统，我们在分析形成性日志之前定义了三个理论驱动的启发性构念：

\begin{description}
\item[\textbf{分析目标转移。}]
分析者取代或实质性地重新定向当前主要分析问题，或者改变希望获得的知识结果。

```
\item[\textbf{工作假设修订。}]
分析者拒绝、替换、限定或实质性地改变一个暂定解释、分析性判断或与决策有关的命题。

\item[\textbf{分析范围细化。}]
分析者改变与相关人群、时间段、地理区域、变量、类别、粒度或数据子集有关的约束，同时通常保留更高层的分析目标。
```

\end{description}

这三个构念是我们面向对话式可视分析所做的理论综合和操作化，而不是既有文献中已经建立的三分法 taxonomy。它们描述的是不同的分析变化对象，因此并不穷尽所有分析变化，也不互斥。一句话可以同时改变分析目标、限定工作假设并调整数据范围。

形成性研究围绕以下三个问题展开：

\begin{description}
\item[\textbf{FQ1.}]
在对话式可视分析中，分析目标、工作假设和分析范围的变化如何被表达？

```
\item[\textbf{FQ2.}]
将三个启发性构念应用于自然交互日志时，会出现哪些复合案例和边界案例？

\item[\textbf{FQ3.}]
从观察到的修订事件中，可以导出哪些对话协调和计算协调需求？
```

\end{description}

\subsection{参与者、任务与日志语料}
\label{sec:formative-procedure-cn}

我们从
\textcolor{red}{[招募来源]}
招募了四名具有数据分析或数据可视化经验的参与者 P1--P4。参与者具有
\textcolor{red}{[经验年限范围]}
年的相关经验，并经常使用
\textcolor{red}{[实际使用的分析工具]}。
所有参与者此前均未使用过 VerbalVis。

参与者使用 VerbalVis 的早期原型探索 Olist 巴西电子商务数据。初始仪表盘包含五个相互协调的视图：月度订单量、品类销售额、各州订单分布、评分分布和配送时间统计。参与者围绕
\textcolor{red}{[形成性研究中的实际任务]}
开展开放式分析，可以自由探索其认为相关的问题、比较、解释和数据子集。研究者没有向参与者介绍三个修订构念，也没有要求参与者产生规定数量的修订或打断。

每次研究持续约
\textcolor{red}{[实验时长]}
分钟。系统记录带时间戳的用户话语、助手话语以及相关交互事件。最终日志目录包含 103 个文件，其中既有完整的交互片段，也有空文件、只包含开场问候的片段，以及系统自动生成的短片段。因此，我们将文件数量视为日志记录机制的产物，而不是独立实验会话或分析任务的数量。

\subsection{候选事件抽取与编码}
\label{sec:formative-analysis-cn}

数据分析采用理论驱动与开放编码相结合的混合策略。分析目标转移、工作假设修订和分析范围细化由既有文献演绎得到；对于不符合这三个操作定义的事件，我们保留额外的开放编码。

我们首先使用大语言模型辅助的筛选程序从日志中提取候选事件。对于每个候选事件，筛选报告保留了用户原话、先前的分析承诺、修订后的分析承诺、一个主标签、零个或多个次标签、交互发生时间以及判定理由。模型生成的标签仅用于候选事件检索，而不被视为最终的 ground truth。

筛选程序共识别出 27 个候选修订事件。由于允许多标签编码，其中 12 个候选事件包含分析目标转移，5 个包含工作假设修订，18 个包含分析范围细化；8 个候选事件同时包含一个以上的修订构念。因此，这些类别计数并不互斥。

在最终分析中，
\textcolor{red}{[编码者人数]}
名研究者结合候选事件的上下文进行复核。只有在新话语之前能够识别出一个正在生效的分析承诺，并且新话语实质性地取代、限定或改变该承诺时，该事件才被保留为
\emph{分析修订事件}。首次建立分析问题或首次提出解释，与修订一个已经存在的问题或解释被明确区分。

最终编码体系包括：

\begin{itemize}
\item 分析目标转移；
\item 工作假设修订；
\item 分析范围细化；
\item 工作假设形成；
\item 方法或操作化修订；
\item 额外证据请求；
\item 自动语音识别纠错；
\item 对话修复或澄清；
\item 普通后续追问；
\item 非分析性打断；
\item 模糊或无法分类。
\end{itemize}

同一个事件可以获得多个修订标签。我们将对理解最新请求最为关键的变化标记为主标签，并将同一事件中同时变化的其他对象标记为次标签。主标签的设置仅用于描述最主要的变化，并不意味着三个类别互斥。

修订语义与交互时间分别编码。候选事件可能发生在正常轮次边界、仪表盘更新完成之后，或者系统语音已经开始但分析操作尚未完成时。通过分别编码，我们可以区分分析过程中
\emph{发生了什么变化}，以及用户
\emph{在什么时候表达该变化}。

编码分歧通过检查先前请求、助手响应、当前仪表盘状态和后续交互进行解决。最终论文需要报告
\textcolor{red}{[实际的一致性处理程序，以及在计算时报告信度指标]}。

\subsection{形成性发现}
\label{sec:formative-findings-cn}

\subsubsection{新的分析问题会引发目标重定向}

目标转移改变的是分析者希望获得的知识结果，而不只是下一步界面操作。在一个事件中，先前的交互主要关注月度订单趋势，参与者随后将分析转向客户体验：

\begin{quote}
“客户分析，客户体验的分析。就是低评分的，时间、周、品类以及配送条件。”
\end{quote}

这句话用对低评分及其潜在影响因素的调查，取代了以订单量为中心的分析。在另一个事件中，参与者在探索各州配送表现后，请求创建支付方式饼图。尽管请求中包含一种可视化形式，但它的分析意义不只是改变图表，而是放弃物流主题并开始一个有关支付行为的新问题。

其他目标变化更加渐进。例如，参与者从一般性地比较各州品类，转向主动寻找评分异常偏低的商品。这说明目标转移既可能改变分析主题，也可能改变希望获得的知识形式或最终分析结果，而不一定更换数据集。

\subsubsection{分析范围沿多个数据维度发生变化}

范围细化通常保留较高层的分析目的，但改变分析所针对的数据对象。参与者会增加地理分组、评分阈值、时间区间、商品品类和时间粒度等约束。

例如，在请求查看总体客户满意度后，一名参与者提出：

\begin{quote}
“先按不同地区来，不同地区的分布来看一下。”
\end{quote}

客户满意度仍然是分析目标，但比较方式被重新组织为不同地区之间的比较。在另一段会话中，参与者先将全局评分限定为一分和二分，随后又将时间限制在 2017 年 9 月至 2018 年 5 月。这两个请求分别细化了评分范围和时间范围，同时保留了对低评分客户体验的总体关注。

日志中的范围变化并不只包含收窄。参与者还会从单个州扩展到全部州，将一个商品品类替换为另一个品类，以及将月度趋势改为按周分析。因此，我们采用更宽泛的
\emph{分析范围细化}，而不是仅使用“范围收窄”。

单独出现一次筛选操作，并不足以证明发生了范围修订。筛选也可能只是执行一个已经建立的分析计划，而没有改变后续推理所适用的数据范围。因此，编码必须结合该操作与先前分析承诺之间的关系。

\subsubsection{工作假设修订要求先前已经存在一个命题}

工作假设相关事件数量较少，并且比目标和范围变化更依赖上下文判断。“AP 是显著低于平均值的离群值”可能是在首次形成一种解释或判断；只有当它限定或替换了一个已经生效的命题时，才能被视为假设修订。

一个更加清晰的事件出现在参与者质疑以配送时间为主的州资源投入标准时：

\begin{quote}
“BA 现在只是配送天数最长。考虑这个销量的因素吗？”
\end{quote}

这句话不只是要求生成另一张图。它质疑了“因为配送时间最长，所以应该优先关注 BA”这一当前命题是否充分，并引入销量作为可能改变结论的条件。因此，这类事件可以编码为对工作假设或决策性判断的限定。

候选分析也揭示了工作假设修订与方法修订之间的边界。一名参与者提出将配送天数和订单量组合成一个比例。这个请求改变了比较各州时使用的指标和操作化方法，但不一定替换了一个解释性命题。因此，我们将
\emph{方法或操作化修订}
保留为额外代码，而不是将所有分析推理方式的变化都强行编码为工作假设修订。

类似地，“为什么 AP 最低”意味着分析从描述转向解释，但如果此前没有已经被接受的解释，它本身并不构成假设修订。结合上下文，这类事件可能属于解释性目标转移、工作假设形成或额外证据请求。

\subsubsection{复合修订会同时改变多个分析对象}

八个候选事件获得了一个以上的修订标签。例如，一名参与者提出：

\begin{quote}
“把排名第三到第五的州按照刚刚那个逻辑再分析一遍，我想找到评分比较低的商品。”
\end{quote}

这个请求一方面将分析范围限制在排名第三至第五的州，另一方面将分析目的从一般性的比较转向主动寻找低评分异常商品。因此，该事件同时包含分析范围细化和分析目标转移。

复合事件不是编码错误，也不是必须被消除的例外。相反，它们说明目标、工作假设和范围是彼此相关但可以区分的分析变化维度，并且可以在一句话中同时变化。这一发现支持多标签编码，也说明系统不应将三个构念实现为互斥的运行时意图类别。

\subsubsection{分析修订需要与对话修复和表达方式变化区分}

部分表面上像是重定向的用户话语，更适合被理解为修复。例如：

\begin{quote}
“我是说，按州，state。”
\end{quote}

这句话是在“按周”和“按州”之间发生语音识别或语义落地错误后进行纠正。它恢复的是用户原来的请求，而不是表达一个新形成的分析方向。

表达方式或可视化形式的改变也需要结合上下文判断。当用户从配送分析转向支付方式分析时，“创建支付方式饼图”同时包含真正的目标转移；但如果用户仅为同一个问题改变图表形式，则更适合编码为方法或表达方式变化。因此，只观察最新一句话，无法可靠判断其修订类型；必须结合先前对话和仪表盘状态。

\subsubsection{修订语义与打断时机相互独立}

大多数候选修订发生在正常轮次边界或仪表盘更新之后，只有少量候选事件出现在系统语音已经开始但分析操作尚未完成时。因此，形成性日志能够支持“探索过程中会发生分析意图修订”这一现象，但不能说明分析修订主要通过自然打断发生。

打断描述的是用户语音与系统语音之间的时间重叠；分析修订描述的是最新话语与当前分析之间的语义关系。用户可能在系统说话时纠正一个识别错误，而不改变分析；也可能等待系统说完后再实质性地改变分析目标。因此，系统设计和后续评估都应将这两个维度分开处理。

\subsection{设计需求}
\label{sec:design-requirements-cn}

理论基础和形成性发现共同导出了四项设计需求。

\paragraph{DR1：结合当前分析承诺解释新话语。}

系统应维护足够的对话和仪表盘上下文，以判断新的请求是在延续、限定还是取代当前分析目标、工作解释或分析范围。系统不能将一句话视为脱离先前分析过程的孤立命令。

\paragraph{DR2：通过可组合操作支持重叠修订。}

一句话可能在重新定向分析目标的同时，改变多个数据约束或限定当前解释。系统因此应支持多个 schema-grounded 分析操作的组合，而不是要求每句话只能映射到一个操作或一个互斥的修订类别。

\paragraph{DR3：区分分析修订、对话修复、证据请求和方法变化。}

语音识别纠错、澄清请求、额外证据请求，以及图表或指标变化，不应自动被解释为分析意图发生变化。系统应保留这些语义差异，使纠错能够恢复用户原来的请求，也避免一次方法变化不必要地取消仍然有效的分析目标。

\paragraph{DR4：在语音、工具执行和仪表盘状态之间协调 supersession。}

在全双工场景中，用户的新请求可能在系统语音、工具生成、查询执行或仪表盘渲染仍然进行时到达。当新请求取代当前响应时，系统应停止过时语音，使依赖旧响应的分析操作失效，拒绝迟到结果，并基于最新已经提交的仪表盘状态重新规划。

最后一项需求来自“分析修订”与“并发系统执行”两个条件的结合。它并不假设所有修订都通过打断发生，而是规定当修订确实在当前响应结束之前到达时，系统还需要提供哪些额外协调机制。

\subsection{形成性证据的适用范围}
\label{sec:formative-scope-cn}

本形成性研究提供的是面向系统设计的证据，而不是对普遍分类体系的验证。四名参与者不足以证明理论饱和，也无法估计各类修订在总体中的出现频率，或者证明三个构念能够覆盖所有形式的分析变化。此外，大语言模型辅助标签仅用于候选事件检索，正式结果仍需结合原始交互上下文完成人工核验。

因此，我们将分析目标转移、工作假设修订和分析范围细化视为具有理论基础、非穷尽且可能重叠的分析视角。形成性证据展示了它们在描述部分修订事件时的作用，揭示了重要的复合案例和边界案例，并为 VerbalVis 的设计提供依据。后续用户研究评估的是 VerbalVis 的全双工交互和协调机制，而不是将三个构念验证为一种普遍适用的分类体系。



\section{Formative Inquiry and Design Requirements}
\label{sec:formative}

We conducted a lightweight formative inquiry to understand how analysts revise
an ongoing investigation during conversational visual analysis and to derive
requirements for a full-duplex visual analytics system. The inquiry was
design-oriented rather than confirmatory. It did not aim to establish an
exhaustive taxonomy of exploratory behavior or estimate the prevalence of
revision forms in a broader population. Instead, we used prior theory to
identify analytically meaningful objects that may change during exploration,
examined how these changes appeared in interaction logs, and refined their
operational boundaries through compound and ambiguous cases.

\subsection{Theory-Informed Framing and Study Questions}
\label{sec:formative-framing}

Exploratory analysis is rarely governed by a fully specified and stable plan.
Sensemaking research describes analysis as an iterative process in which people
construct, inspect, and revise task-specific representations
\cite{russell1993cost,pirolli2005sensemaking}. Information-seeking research
similarly shows that questions and queries evolve as new information is
encountered~\cite{bates1989berrypicking,vakkari2001changes}. In visual
analytics, observations and insights may generate new questions, redirect
subsequent exploration, and decompose broad goals into more focused analytical
tasks~\cite{sacha2014knowledge,battle2019characterizing,
lam2018bridging}.

Prior research also provides a foundation for changes to provisional
explanations. Data--Frame Theory describes sensemaking as a reciprocal
relationship between evidence and an explanatory frame; new evidence may lead
an analyst to elaborate, question, compare, or replace the current frame
\cite{klein2007dataframe,pontis2016influence}. Scientific-reasoning research
distinguishes search within a hypothesis space from search for experiments or
evidence with which to evaluate hypotheses~\cite{klahr1988dual}. Visual
analytics models likewise include hypothesis generation, verification, and
falsification in iterative knowledge generation
\cite{sacha2014knowledge,shrinivasan2008supporting}. Because a revised
explanation remains provisional rather than necessarily correct, we use the
term \emph{Working-Hypothesis Revision}
\cite{chinn1993anomalous,thagard1989explanatory}.

A third literature stream concerns progressive focusing. Information Foraging
Theory and interactive information-retrieval research describe how initially
broad information needs become more specific through search-space reduction,
query reformulation, and the selection of increasingly relevant information
patches~\cite{pirolli1999information,bates1989berrypicking,
vakkari2001changes}. Visualization task research further distinguishes the
purpose of an analysis from the data target and interaction method through
which that purpose is pursued~\cite{brehmer2013multilevel,
lam2018bridging}. Systems such as Voyager operationalize progressive
specification through faceted exploration of data and visual properties
\cite{wongsuphasawat2016voyager}.

Based on these traditions, we specified three theory-informed sensitizing
concepts before analyzing the formative logs:

\begin{description}
\item[\textbf{Analytical Goal Shift.}]
The analyst supersedes or materially reorients the primary analytical
question or desired knowledge outcome.

```
\item[\textbf{Working-Hypothesis Revision.}]
The analyst rejects, replaces, qualifies, or materially alters a
provisional explanation, interpretation, or decision-relevant
proposition.

\item[\textbf{Analytical Scope Refinement.}]
The analyst changes constraints over the relevant population, time period,
geography, variables, categories, granularity, or data subset while
generally preserving the higher-level analytical objective.
```

\end{description}

These constructs are our synthesis and operationalization for conversational
visual analytics rather than a previously established three-part taxonomy.
They describe different objects of analytical change and are therefore
non-exhaustive and potentially overlapping. One utterance may simultaneously
redirect the analytical goal, qualify a working hypothesis, and refine the
data scope.

We investigated three formative questions:

\begin{description}
\item[\textbf{FQ1.}]
How are changes to analytical goals, working hypotheses, and analytical
scope expressed during conversational visual analysis?

```
\item[\textbf{FQ2.}]
What compound and boundary cases arise when the three sensitizing concepts
are applied to natural interaction logs?

\item[\textbf{FQ3.}]
What requirements for conversational and computational coordination follow
from the observed revision episodes?
```

\end{description}

\subsection{Participants, Task, and Log Corpus}
\label{sec:formative-procedure}

We recruited four participants (P1--P4) with prior experience in data analysis
or visualization from
\textcolor{red}{[RECRUITMENT SOURCE]}. Participants reported
\textcolor{red}{[RANGE]} years of experience and regularly used
\textcolor{red}{[ACTUAL ANALYSIS TOOLS]}. None had previously used VerbalVis.

Participants used an early VerbalVis prototype to explore the Olist Brazilian
e-commerce dataset. The initial dashboard contained coordinated views of
monthly order volume, category-level sales, state-level order distribution,
review-score distribution, and delivery-time statistics. Participants were
given an open-ended analytical task concerning
\textcolor{red}{[ACTUAL FORMATIVE TASK]} and were free to pursue questions,
comparisons, explanations, and data subsets that they considered relevant.
They were not instructed to produce the three revision constructs or to
interrupt the assistant a specified number of times.

Each session lasted approximately
\textcolor{red}{[SESSION DURATION]} minutes. The system recorded timestamped
user and assistant utterances together with relevant interaction events. The
resulting directory contained 103 log files. These files included complete
interaction segments as well as empty files, greeting-only fragments, and
short system-generated segments. We therefore treated the number of files as
a property of the logging process rather than as the number of independent
sessions or analytical trials.

\subsection{Candidate Extraction and Coding}
\label{sec:formative-analysis}

The analysis followed a hybrid deductive--inductive strategy. The three
revision constructs were specified deductively from the literature, while
additional codes were retained for episodes that did not fit their operational
definitions.

We used an LLM-assisted screening pass to retrieve candidate episodes from the
logs. For every candidate, the screening report contained the exact user
utterance, the preceding analytical commitment, the proposed revised
commitment, one primary and zero or more secondary revision labels, the
interaction timing, and a rationale. The model-generated labels were treated
as candidate annotations rather than ground truth.

The screening pass identified 27 candidate revision episodes. Because
multi-label coding was permitted, 12 candidates involved Analytical Goal
Shift, five involved Working-Hypothesis Revision, and 18 involved Analytical
Scope Refinement; eight candidates involved more than one construct. These
counts describe the screening output and are not mutually exclusive.

For the final analysis,
\textcolor{red}{[NUMBER OF CODERS]} researchers reviewed the candidate
episodes against their surrounding dialogue. An episode was retained as an
\emph{analytical revision} only when an active analytical commitment could be
identified before the utterance and the utterance materially superseded,
qualified, or altered that commitment. Merely establishing an initial question
or explanation was distinguished from revising an existing one.

The coding scheme included:

\begin{itemize}
\item Analytical Goal Shift;
\item Working-Hypothesis Revision;
\item Analytical Scope Refinement;
\item Working-Hypothesis Formation;
\item Method or Operationalization Revision;
\item Request for Additional Evidence;
\item Automatic-Speech-Recognition Correction;
\item Conversational Repair or Clarification;
\item Ordinary Follow-Up;
\item Non-Analytical Barge-In; and
\item Ambiguous or Unclassified.
\end{itemize}

A single episode could receive multiple revision labels. We assigned one
primary label to the change most consequential for interpreting the latest
request and zero or more secondary labels to other simultaneously revised
objects. The primary label did not imply that the categories were mutually
exclusive.

Interaction timing was coded independently from revision semantics. Candidate
episodes occurred at ordinary turn boundaries, after a dashboard update, or
after system speech but before an analytical action had completed. This
separation allowed us to distinguish \emph{what} changed in the investigation
from \emph{when} the user expressed the change.

The coders resolved disagreements by examining the preceding request, the
assistant's response, the current dashboard state, and the subsequent
interaction. The final paper should report
\textcolor{red}{[AGREEMENT PROCEDURE AND RELIABILITY, IF CALCULATED]}.

\subsection{Formative Findings}
\label{sec:formative-findings}

\subsubsection{Analytical goals were redirected as new questions emerged}

Goal shifts changed the knowledge outcome being pursued rather than merely the
next interface operation. In one episode, the prior interaction concerned
monthly order trends. The participant redirected the analysis toward customer
experience:

\begin{quote}
``Customer experience analysis---the low-rated orders, including their time,
category, and delivery conditions.''
\end{quote}

The utterance replaced an order-volume-oriented analysis with an investigation
of low ratings and their possible contributing factors. In another episode,
after exploring geographic delivery performance, a participant requested a
payment-method pie chart. Although the request contained a representation
choice, its analytical significance came from abandoning the logistics topic
and beginning an unrelated investigation of payment behavior.

Other goal shifts were more incremental. A participant moved from generally
comparing state-level product categories to actively seeking products with
unusually low ratings. Such episodes show that goal shifts may change the
topic, the desired form of knowledge, or the intended analytical outcome
without necessarily changing the dataset.

\subsubsection{Scope refinement occurred along several data dimensions}

Scope refinements preserved the broader analytical purpose while changing the
data target. Participants introduced geographic groupings, rating thresholds,
time intervals, product categories, and temporal granularity.

For example, after requesting an overall view of customer satisfaction, one
participant stated:

\begin{quote}
``First, let us look at the distribution by region.''
\end{quote}

The satisfaction objective remained active, but the relevant comparison was
reorganized around geographic regions. In another session, a participant
restricted the dashboard to one- and two-star orders and subsequently limited
the analysis to September 2017 through May 2018. These utterances successively
refined the rating and temporal scope while preserving the broader concern
with low-rating customer experience.

The logs also contained scope broadening, substitution, and changes in
granularity. Participants moved from one state to all states, replaced one
product category with another, and changed a monthly trend into a weekly
analysis. These cases motivated the term \emph{Scope Refinement} rather than
the narrower \emph{Scope Narrowing}.

A dashboard operation alone was not considered sufficient evidence of scope
revision. A filter could implement a previously established plan without
changing the intended scope of subsequent reasoning. Coding therefore depended
on the relationship between the operation and the prior analytical commitment.

\subsubsection{Working-hypothesis revision required an existing proposition}

Working-hypothesis episodes were less frequent and required stricter contextual
judgment. A statement such as ``AP is an outlier below the average'' may
establish an initial interpretation, but it constitutes revision only when it
qualifies or replaces an already active proposition.

A clearer case occurred when a participant questioned a state-prioritization
criterion based primarily on delivery time:

\begin{quote}
``BA only has the longest delivery time. Does this take sales volume into
account?''
\end{quote}

The utterance did not merely request another chart. It challenged the
sufficiency of the active proposition that Bahia should be prioritized because
of its delivery time and introduced sales volume as a condition that might
alter that conclusion. We coded such cases as qualification of a working
hypothesis or decision-relevant interpretation.

The candidate analysis also exposed a boundary between hypothesis revision
and method revision. One participant proposed combining delivery days and
order volume into a ratio. This changed the metric and analytical
operationalization used to evaluate states; it did not necessarily replace an
explanatory proposition. We therefore retained
\emph{Method or Operationalization Revision} as a residual code rather than
forcing every change in analytical reasoning into Working-Hypothesis Revision.

Similarly, asking ``Why is AP the lowest?'' moves from description toward
explanation but does not by itself revise a hypothesis if no prior explanation
has been adopted. Such an episode may represent an explanatory goal shift,
hypothesis formation, or a request for additional evidence depending on the
surrounding context.

\subsubsection{Compound revisions changed multiple analytical objects}

Eight candidate episodes received more than one revision label. For example, a
participant stated:

\begin{quote}
``Apply the same analysis to the third- through fifth-ranked states; I want to
find products with relatively low ratings.''
\end{quote}

The request simultaneously restricted the analysis to a subset of states and
redirected the purpose from general comparison to active anomaly seeking. We
therefore treated it as both Analytical Scope Refinement and Analytical Goal
Shift.

Compound episodes were not treated as coding errors or exceptional cases.
Instead, they showed that goal, working hypothesis, and scope are related but
distinguishable dimensions that can change together in one utterance. This
motivated multi-label coding and argues against implementing the three
constructs as mutually exclusive runtime intent classes.

\subsubsection{Revision had to be distinguished from repair and representation
change}

Some utterances that appeared to redirect the system were better understood as
repair. For example:

\begin{quote}
``I mean by state---state.''
\end{quote}

The utterance corrected a grounding or speech-recognition error between weekly
aggregation and state-level grouping. It restored the intended request rather
than expressing a newly developed analytical direction.

Representation changes were also context dependent. A request for a pie chart
could accompany a genuine goal shift when the user changed from delivery
analysis to payment behavior. In contrast, changing only the chart form for an
existing question would be coded as a method or representation change. The
latest utterance could therefore not be coded reliably without its prior
dialogue and dashboard context.

\subsubsection{Revision semantics and interruption timing were orthogonal}

Most candidate revisions occurred at ordinary turn boundaries or after a
dashboard update, while only a small number were detected after system speech
but before analytical completion. The formative evidence therefore supports
the occurrence of analytical revision during exploratory interaction, but does
not imply that revisions predominantly occur through barge-in.

Barge-in describes the temporal overlap between user and system speech.
Analytical revision describes the semantic relationship between a new
utterance and the active investigation. A user may interrupt to correct a
misrecognized term without changing the analysis, or may wait until the
assistant has finished before substantially redirecting the goal. The two
dimensions should therefore be modeled and evaluated separately.

\subsection{Design Requirements}
\label{sec:design-requirements}

The theoretical framing and formative findings informed four design
requirements.

\paragraph{DR1: Interpret new utterances relative to active analytical
commitments.}

The system should maintain sufficient dialogue and dashboard context to
determine whether a new request preserves, qualifies, or supersedes the active
goal, working interpretation, or scope. An utterance should not be interpreted
as an isolated command independent of the investigation that precedes it.

\paragraph{DR2: Support overlapping revisions through composable actions.}

A single utterance may redirect the analytical goal while simultaneously
changing several data constraints or qualifying an interpretation. The system
should therefore support composable, schema-grounded analytical actions rather
than require each utterance to map to one operation or one mutually exclusive
revision class.

\paragraph{DR3: Distinguish analytical revision from repair, evidence seeking,
and method change.}

Recognition corrections, clarification requests, requests for further
evidence, and changes in chart or metric should not automatically be treated
as changes to analytical intent. The system should preserve these distinctions
so that a repair restores the intended request and a method change does not
unnecessarily discard a still-valid analytical objective.

\paragraph{DR4: Coordinate supersession across speech, tools, and dashboard
state.}

In a full-duplex setting, a revised request may arrive while system speech,
tool generation, query execution, or dashboard rendering is still active.
When the new request supersedes the active response, obsolete speech should be
stopped, response-dependent analytical actions should be invalidated, late
results should be rejected, and replanning should begin from the latest
committed dashboard state.

This final requirement follows from combining the observed phenomenon of
analytical revision with concurrent system execution. It does not assume that
all revisions occur as barge-ins; rather, it specifies the additional
coordination needed when a revision does arrive before the current response
has completed.

\subsection{Scope of the Formative Evidence}
\label{sec:formative-scope}

The formative inquiry provides design-oriented evidence rather than validation
of a general taxonomy. Four participants cannot establish theoretical
saturation, estimate population-level frequencies, or demonstrate that the
three constructs cover all forms of analytical change. Moreover, the
LLM-assisted annotations were used for candidate retrieval and require human
verification against the original interaction context.

We therefore treat Analytical Goal Shift, Working-Hypothesis Revision, and
Analytical Scope Refinement as theory-informed, non-exhaustive, and potentially
overlapping analytical lenses. The formative evidence illustrates their
usefulness, exposes important compound and boundary cases, and informs the
design of VerbalVis. The subsequent user study evaluates the full-duplex
interaction and orchestration mechanisms rather than testing the three
constructs as a universal classification



\section{Formative Inquiry and Design Requirements}
\label{sec:formative}

We conducted a lightweight formative inquiry to understand how analysts revise
an ongoing investigation during conversational visual analysis and to derive
requirements for a full-duplex visual analytics system. The inquiry was
design-oriented rather than confirmatory. It did not aim to establish an
exhaustive taxonomy of exploratory behavior or estimate the prevalence of
revision forms in a broader population. Instead, we used prior theory to
identify analytically meaningful objects that may change during exploration,
examined how these changes appeared in interaction logs, and refined their
operational boundaries through compound and ambiguous cases.

\subsection{Theory-Informed Framing and Study Questions}
\label{sec:formative-framing}

Exploratory analysis is rarely governed by a fully specified and stable plan.
Sensemaking research describes analysis as an iterative process in which people
construct, inspect, and revise task-specific representations
\cite{russell1993cost,pirolli2005sensemaking}. Information-seeking research
similarly shows that questions and queries evolve as new information is
encountered~\cite{bates1989berrypicking,vakkari2001changes}. In visual
analytics, observations and insights may generate new questions, redirect
subsequent exploration, and decompose broad goals into more focused analytical
tasks~\cite{sacha2014knowledge,battle2019characterizing,
lam2018bridging}.

Prior research also provides a foundation for changes to provisional
explanations. Data--Frame Theory describes sensemaking as a reciprocal
relationship between evidence and an explanatory frame; new evidence may lead
an analyst to elaborate, question, compare, or replace the current frame
\cite{klein2007dataframe,pontis2016influence}. Scientific-reasoning research
distinguishes search within a hypothesis space from search for experiments or
evidence with which to evaluate hypotheses~\cite{klahr1988dual}. Visual
analytics models likewise include hypothesis generation, verification, and
falsification in iterative knowledge generation
\cite{sacha2014knowledge,shrinivasan2008supporting}. Because a revised
explanation remains provisional rather than necessarily correct, we use the
term \emph{Working-Hypothesis Revision}
\cite{chinn1993anomalous,thagard1989explanatory}.

A third literature stream concerns progressive focusing. Information Foraging
Theory and interactive information-retrieval research describe how initially
broad information needs become more specific through search-space reduction,
query reformulation, and the selection of increasingly relevant information
patches~\cite{pirolli1999information,bates1989berrypicking,
vakkari2001changes}. Visualization task research further distinguishes the
purpose of an analysis from the data target and interaction method through
which that purpose is pursued~\cite{brehmer2013multilevel,
lam2018bridging}. Systems such as Voyager operationalize progressive
specification through faceted exploration of data and visual properties
\cite{wongsuphasawat2016voyager}.

Based on these traditions, we specified three theory-informed sensitizing
concepts before analyzing the formative logs:

\begin{description}
\item[\textbf{Analytical Goal Shift.}]
The analyst supersedes or materially reorients the primary analytical
question or desired knowledge outcome.

```
\item[\textbf{Working-Hypothesis Revision.}]
The analyst rejects, replaces, qualifies, or materially alters a
provisional explanation, interpretation, or decision-relevant
proposition.

\item[\textbf{Analytical Scope Refinement.}]
The analyst changes constraints over the relevant population, time period,
geography, variables, categories, granularity, or data subset while
generally preserving the higher-level analytical objective.
```

\end{description}

These constructs are our synthesis and operationalization for conversational
visual analytics rather than a previously established three-part taxonomy.
They describe different objects of analytical change and are therefore
non-exhaustive and potentially overlapping. One utterance may simultaneously
redirect the analytical goal, qualify a working hypothesis, and refine the
data scope.

We investigated three formative questions:

\begin{description}
\item[\textbf{FQ1.}]
How are changes to analytical goals, working hypotheses, and analytical
scope expressed during conversational visual analysis?

```
\item[\textbf{FQ2.}]
What compound and boundary cases arise when the three sensitizing concepts
are applied to natural interaction logs?

\item[\textbf{FQ3.}]
What requirements for conversational and computational coordination follow
from the observed revision episodes?
```

\end{description}

\subsection{Participants, Task, and Log Corpus}
\label{sec:formative-procedure}

We recruited four participants (P1--P4) with prior experience in data analysis
or visualization from
\textcolor{red}{[RECRUITMENT SOURCE]}. Participants reported
\textcolor{red}{[RANGE]} years of experience and regularly used
\textcolor{red}{[ACTUAL ANALYSIS TOOLS]}. None had previously used VerbalVis.

Participants used an early VerbalVis prototype to explore the Olist Brazilian
e-commerce dataset. The initial dashboard contained coordinated views of
monthly order volume, category-level sales, state-level order distribution,
review-score distribution, and delivery-time statistics. Participants were
given an open-ended analytical task concerning
\textcolor{red}{[ACTUAL FORMATIVE TASK]} and were free to pursue questions,
comparisons, explanations, and data subsets that they considered relevant.
They were not instructed to produce the three revision constructs or to
interrupt the assistant a specified number of times.

Each session lasted approximately
\textcolor{red}{[SESSION DURATION]} minutes. The system recorded timestamped
user and assistant utterances together with relevant interaction events. The
resulting directory contained 103 log files. These files included complete
interaction segments as well as empty files, greeting-only fragments, and
short system-generated segments. We therefore treated the number of files as
a property of the logging process rather than as the number of independent
sessions or analytical trials.

\subsection{Candidate Extraction and Coding}
\label{sec:formative-analysis}

The analysis followed a hybrid deductive--inductive strategy. The three
revision constructs were specified deductively from the literature, while
additional codes were retained for episodes that did not fit their operational
definitions.

We used an LLM-assisted screening pass to retrieve candidate episodes from the
logs. For every candidate, the screening report contained the exact user
utterance, the preceding analytical commitment, the proposed revised
commitment, one primary and zero or more secondary revision labels, the
interaction timing, and a rationale. The model-generated labels were treated
as candidate annotations rather than ground truth.

The screening pass identified 27 candidate revision episodes. Because
multi-label coding was permitted, 12 candidates involved Analytical Goal
Shift, five involved Working-Hypothesis Revision, and 18 involved Analytical
Scope Refinement; eight candidates involved more than one construct. These
counts describe the screening output and are not mutually exclusive.

For the final analysis,
\textcolor{red}{[NUMBER OF CODERS]} researchers reviewed the candidate
episodes against their surrounding dialogue. An episode was retained as an
\emph{analytical revision} only when an active analytical commitment could be
identified before the utterance and the utterance materially superseded,
qualified, or altered that commitment. Merely establishing an initial question
or explanation was distinguished from revising an existing one.

The coding scheme included:

\begin{itemize}
\item Analytical Goal Shift;
\item Working-Hypothesis Revision;
\item Analytical Scope Refinement;
\item Working-Hypothesis Formation;
\item Method or Operationalization Revision;
\item Request for Additional Evidence;
\item Automatic-Speech-Recognition Correction;
\item Conversational Repair or Clarification;
\item Ordinary Follow-Up;
\item Non-Analytical Barge-In; and
\item Ambiguous or Unclassified.
\end{itemize}

A single episode could receive multiple revision labels. We assigned one
primary label to the change most consequential for interpreting the latest
request and zero or more secondary labels to other simultaneously revised
objects. The primary label did not imply that the categories were mutually
exclusive.

Interaction timing was coded independently from revision semantics. Candidate
episodes occurred at ordinary turn boundaries, after a dashboard update, or
after system speech but before an analytical action had completed. This
separation allowed us to distinguish \emph{what} changed in the investigation
from \emph{when} the user expressed the change.

The coders resolved disagreements by examining the preceding request, the
assistant's response, the current dashboard state, and the subsequent
interaction. The final paper should report
\textcolor{red}{[AGREEMENT PROCEDURE AND RELIABILITY, IF CALCULATED]}.

\subsection{Formative Findings}
\label{sec:formative-findings}

\subsubsection{Analytical goals were redirected as new questions emerged}

Goal shifts changed the knowledge outcome being pursued rather than merely the
next interface operation. In one episode, the prior interaction concerned
monthly order trends. The participant redirected the analysis toward customer
experience:

\begin{quote}
``Customer experience analysis---the low-rated orders, including their time,
category, and delivery conditions.''
\end{quote}

The utterance replaced an order-volume-oriented analysis with an investigation
of low ratings and their possible contributing factors. In another episode,
after exploring geographic delivery performance, a participant requested a
payment-method pie chart. Although the request contained a representation
choice, its analytical significance came from abandoning the logistics topic
and beginning an unrelated investigation of payment behavior.

Other goal shifts were more incremental. A participant moved from generally
comparing state-level product categories to actively seeking products with
unusually low ratings. Such episodes show that goal shifts may change the
topic, the desired form of knowledge, or the intended analytical outcome
without necessarily changing the dataset.

\subsubsection{Scope refinement occurred along several data dimensions}

Scope refinements preserved the broader analytical purpose while changing the
data target. Participants introduced geographic groupings, rating thresholds,
time intervals, product categories, and temporal granularity.

For example, after requesting an overall view of customer satisfaction, one
participant stated:

\begin{quote}
``First, let us look at the distribution by region.''
\end{quote}

The satisfaction objective remained active, but the relevant comparison was
reorganized around geographic regions. In another session, a participant
restricted the dashboard to one- and two-star orders and subsequently limited
the analysis to September 2017 through May 2018. These utterances successively
refined the rating and temporal scope while preserving the broader concern
with low-rating customer experience.

The logs also contained scope broadening, substitution, and changes in
granularity. Participants moved from one state to all states, replaced one
product category with another, and changed a monthly trend into a weekly
analysis. These cases motivated the term \emph{Scope Refinement} rather than
the narrower \emph{Scope Narrowing}.

A dashboard operation alone was not considered sufficient evidence of scope
revision. A filter could implement a previously established plan without
changing the intended scope of subsequent reasoning. Coding therefore depended
on the relationship between the operation and the prior analytical commitment.

\subsubsection{Working-hypothesis revision required an existing proposition}

Working-hypothesis episodes were less frequent and required stricter contextual
judgment. A statement such as ``AP is an outlier below the average'' may
establish an initial interpretation, but it constitutes revision only when it
qualifies or replaces an already active proposition.

A clearer case occurred when a participant questioned a state-prioritization
criterion based primarily on delivery time:

\begin{quote}
``BA only has the longest delivery time. Does this take sales volume into
account?''
\end{quote}

The utterance did not merely request another chart. It challenged the
sufficiency of the active proposition that Bahia should be prioritized because
of its delivery time and introduced sales volume as a condition that might
alter that conclusion. We coded such cases as qualification of a working
hypothesis or decision-relevant interpretation.

The candidate analysis also exposed a boundary between hypothesis revision
and method revision. One participant proposed combining delivery days and
order volume into a ratio. This changed the metric and analytical
operationalization used to evaluate states; it did not necessarily replace an
explanatory proposition. We therefore retained
\emph{Method or Operationalization Revision} as a residual code rather than
forcing every change in analytical reasoning into Working-Hypothesis Revision.

Similarly, asking ``Why is AP the lowest?'' moves from description toward
explanation but does not by itself revise a hypothesis if no prior explanation
has been adopted. Such an episode may represent an explanatory goal shift,
hypothesis formation, or a request for additional evidence depending on the
surrounding context.

\subsubsection{Compound revisions changed multiple analytical objects}

Eight candidate episodes received more than one revision label. For example, a
participant stated:

\begin{quote}
``Apply the same analysis to the third- through fifth-ranked states; I want to
find products with relatively low ratings.''
\end{quote}

The request simultaneously restricted the analysis to a subset of states and
redirected the purpose from general comparison to active anomaly seeking. We
therefore treated it as both Analytical Scope Refinement and Analytical Goal
Shift.

Compound episodes were not treated as coding errors or exceptional cases.
Instead, they showed that goal, working hypothesis, and scope are related but
distinguishable dimensions that can change together in one utterance. This
motivated multi-label coding and argues against implementing the three
constructs as mutually exclusive runtime intent classes.

\subsubsection{Revision had to be distinguished from repair and representation
change}

Some utterances that appeared to redirect the system were better understood as
repair. For example:

\begin{quote}
``I mean by state---state.''
\end{quote}

The utterance corrected a grounding or speech-recognition error between weekly
aggregation and state-level grouping. It restored the intended request rather
than expressing a newly developed analytical direction.

Representation changes were also context dependent. A request for a pie chart
could accompany a genuine goal shift when the user changed from delivery
analysis to payment behavior. In contrast, changing only the chart form for an
existing question would be coded as a method or representation change. The
latest utterance could therefore not be coded reliably without its prior
dialogue and dashboard context.

\subsubsection{Revision semantics and interruption timing were orthogonal}

Most candidate revisions occurred at ordinary turn boundaries or after a
dashboard update, while only a small number were detected after system speech
but before analytical completion. The formative evidence therefore supports
the occurrence of analytical revision during exploratory interaction, but does
not imply that revisions predominantly occur through barge-in.

Barge-in describes the temporal overlap between user and system speech.
Analytical revision describes the semantic relationship between a new
utterance and the active investigation. A user may interrupt to correct a
misrecognized term without changing the analysis, or may wait until the
assistant has finished before substantially redirecting the goal. The two
dimensions should therefore be modeled and evaluated separately.

\subsection{Design Requirements}
\label{sec:design-requirements}

The theoretical framing and formative findings informed four design
requirements.

\paragraph{DR1: Interpret new utterances relative to active analytical
commitments.}

The system should maintain sufficient dialogue and dashboard context to
determine whether a new request preserves, qualifies, or supersedes the active
goal, working interpretation, or scope. An utterance should not be interpreted
as an isolated command independent of the investigation that precedes it.

\paragraph{DR2: Support overlapping revisions through composable actions.}

A single utterance may redirect the analytical goal while simultaneously
changing several data constraints or qualifying an interpretation. The system
should therefore support composable, schema-grounded analytical actions rather
than require each utterance to map to one operation or one mutually exclusive
revision class.

\paragraph{DR3: Distinguish analytical revision from repair, evidence seeking,
and method change.}

Recognition corrections, clarification requests, requests for further
evidence, and changes in chart or metric should not automatically be treated
as changes to analytical intent. The system should preserve these distinctions
so that a repair restores the intended request and a method change does not
unnecessarily discard a still-valid analytical objective.

\paragraph{DR4: Coordinate supersession across speech, tools, and dashboard
state.}

In a full-duplex setting, a revised request may arrive while system speech,
tool generation, query execution, or dashboard rendering is still active.
When the new request supersedes the active response, obsolete speech should be
stopped, response-dependent analytical actions should be invalidated, late
results should be rejected, and replanning should begin from the latest
committed dashboard state.

This final requirement follows from combining the observed phenomenon of
analytical revision with concurrent system execution. It does not assume that
all revisions occur as barge-ins; rather, it specifies the additional
coordination needed when a revision does arrive before the current response
has completed.

\subsection{Scope of the Formative Evidence}
\label{sec:formative-scope}

The formative inquiry provides design-oriented evidence rather than validation
of a general taxonomy. Four participants cannot establish theoretical
saturation, estimate population-level frequencies, or demonstrate that the
three constructs cover all forms of analytical change. Moreover, the
LLM-assisted annotations were used for candidate retrieval and require human
verification against the original interaction context.

We therefore treat Analytical Goal Shift, Working-Hypothesis Revision, and
Analytical Scope Refinement as theory-informed, non-exhaustive, and potentially
overlapping analytical lenses. The formative evidence illustrates their
usefulness, exposes important compound and boundary cases, and informs the
design of VerbalVis. The subsequent user study evaluates the full-duplex
interaction and orchestration mechanisms rather than testing the three
constructs as a universal classification.



\section{Formative Inquiry and Design Requirements}
\label{sec:formative}

We conducted a lightweight formative inquiry to understand how analysts revise
an ongoing investigation during conversational visual analysis and to derive
requirements for a full-duplex visual analytics system. The inquiry was
design-oriented rather than confirmatory. It did not aim to establish an
exhaustive taxonomy of exploratory behavior or estimate the prevalence of
revision forms in a broader population. Instead, we used prior theory to
identify analytically meaningful objects that may change during exploration,
examined how these changes appeared in interaction logs, and refined their
operational boundaries through compound and ambiguous cases.

\subsection{Theory-Informed Framing and Study Questions}
\label{sec:formative-framing}

Exploratory analysis is rarely governed by a fully specified and stable plan.
Sensemaking research describes analysis as an iterative process in which people
construct, inspect, and revise task-specific representations
\cite{russell1993cost,pirolli2005sensemaking}. Information-seeking research
similarly shows that questions and queries evolve as new information is
encountered~\cite{bates1989berrypicking,vakkari2001changes}. In visual
analytics, observations and insights may generate new questions, redirect
subsequent exploration, and decompose broad goals into more focused analytical
tasks~\cite{sacha2014knowledge,battle2019characterizing,
lam2018bridging}.

Prior research also provides a foundation for changes to provisional
explanations. Data--Frame Theory describes sensemaking as a reciprocal
relationship between evidence and an explanatory frame; new evidence may lead
an analyst to elaborate, question, compare, or replace the current frame
\cite{klein2007dataframe,pontis2016influence}. Scientific-reasoning research
distinguishes search within a hypothesis space from search for experiments or
evidence with which to evaluate hypotheses~\cite{klahr1988dual}. Visual
analytics models likewise include hypothesis generation, verification, and
falsification in iterative knowledge generation
\cite{sacha2014knowledge,shrinivasan2008supporting}. Because a revised
explanation remains provisional rather than necessarily correct, we use the
term \emph{Working-Hypothesis Revision}
\cite{chinn1993anomalous,thagard1989explanatory}.

A third literature stream concerns progressive focusing. Information Foraging
Theory and interactive information-retrieval research describe how initially
broad information needs become more specific through search-space reduction,
query reformulation, and the selection of increasingly relevant information
patches~\cite{pirolli1999information,bates1989berrypicking,
vakkari2001changes}. Visualization task research further distinguishes the
purpose of an analysis from the data target and interaction method through
which that purpose is pursued~\cite{brehmer2013multilevel,
lam2018bridging}. Systems such as Voyager operationalize progressive
specification through faceted exploration of data and visual properties
\cite{wongsuphasawat2016voyager}.

Based on these traditions, we specified three theory-informed sensitizing
concepts before analyzing the formative logs:

\begin{description}
\item[\textbf{Analytical Goal Shift.}]
The analyst supersedes or materially reorients the primary analytical
question or desired knowledge outcome.

```
\item[\textbf{Working-Hypothesis Revision.}]
The analyst rejects, replaces, qualifies, or materially alters a
provisional explanation, interpretation, or decision-relevant
proposition.

\item[\textbf{Analytical Scope Refinement.}]
The analyst changes constraints over the relevant population, time period,
geography, variables, categories, granularity, or data subset while
generally preserving the higher-level analytical objective.
```

\end{description}

These constructs are our synthesis and operationalization for conversational
visual analytics rather than a previously established three-part taxonomy.
They describe different objects of analytical change and are therefore
non-exhaustive and potentially overlapping. One utterance may simultaneously
redirect the analytical goal, qualify a working hypothesis, and refine the
data scope.

We investigated three formative questions:

\begin{description}
\item[\textbf{FQ1.}]
How are changes to analytical goals, working hypotheses, and analytical
scope expressed during conversational visual analysis?

```
\item[\textbf{FQ2.}]
What compound and boundary cases arise when the three sensitizing concepts
are applied to natural interaction logs?

\item[\textbf{FQ3.}]
What requirements for conversational and computational coordination follow
from the observed revision episodes?
```

\end{description}

\subsection{Participants, Task, and Log Corpus}
\label{sec:formative-procedure}

We recruited four participants (P1--P4) with prior experience in data analysis
or visualization from
\textcolor{red}{[RECRUITMENT SOURCE]}. Participants reported
\textcolor{red}{[RANGE]} years of experience and regularly used
\textcolor{red}{[ACTUAL ANALYSIS TOOLS]}. None had previously used VerbalVis.

Participants used an early VerbalVis prototype to explore the Olist Brazilian
e-commerce dataset. The initial dashboard contained coordinated views of
monthly order volume, category-level sales, state-level order distribution,
review-score distribution, and delivery-time statistics. Participants were
given an open-ended analytical task concerning
\textcolor{red}{[ACTUAL FORMATIVE TASK]} and were free to pursue questions,
comparisons, explanations, and data subsets that they considered relevant.
They were not instructed to produce the three revision constructs or to
interrupt the assistant a specified number of times.

Each session lasted approximately
\textcolor{red}{[SESSION DURATION]} minutes. The system recorded timestamped
user and assistant utterances together with relevant interaction events. The
resulting directory contained 103 log files. These files included complete
interaction segments as well as empty files, greeting-only fragments, and
short system-generated segments. We therefore treated the number of files as
a property of the logging process rather than as the number of independent
sessions or analytical trials.

\subsection{Candidate Extraction and Coding}
\label{sec:formative-analysis}

The analysis followed a hybrid deductive--inductive strategy. The three
revision constructs were specified deductively from the literature, while
additional codes were retained for episodes that did not fit their operational
definitions.

We used an LLM-assisted screening pass to retrieve candidate episodes from the
logs. For every candidate, the screening report contained the exact user
utterance, the preceding analytical commitment, the proposed revised
commitment, one primary and zero or more secondary revision labels, the
interaction timing, and a rationale. The model-generated labels were treated
as candidate annotations rather than ground truth.

The screening pass identified 27 candidate revision episodes. Because
multi-label coding was permitted, 12 candidates involved Analytical Goal
Shift, five involved Working-Hypothesis Revision, and 18 involved Analytical
Scope Refinement; eight candidates involved more than one construct. These
counts describe the screening output and are not mutually exclusive.

For the final analysis,
\textcolor{red}{[NUMBER OF CODERS]} researchers reviewed the candidate
episodes against their surrounding dialogue. An episode was retained as an
\emph{analytical revision} only when an active analytical commitment could be
identified before the utterance and the utterance materially superseded,
qualified, or altered that commitment. Merely establishing an initial question
or explanation was distinguished from revising an existing one.

The coding scheme included:

\begin{itemize}
\item Analytical Goal Shift;
\item Working-Hypothesis Revision;
\item Analytical Scope Refinement;
\item Working-Hypothesis Formation;
\item Method or Operationalization Revision;
\item Request for Additional Evidence;
\item Automatic-Speech-Recognition Correction;
\item Conversational Repair or Clarification;
\item Ordinary Follow-Up;
\item Non-Analytical Barge-In; and
\item Ambiguous or Unclassified.
\end{itemize}

A single episode could receive multiple revision labels. We assigned one
primary label to the change most consequential for interpreting the latest
request and zero or more secondary labels to other simultaneously revised
objects. The primary label did not imply that the categories were mutually
exclusive.

Interaction timing was coded independently from revision semantics. Candidate
episodes occurred at ordinary turn boundaries, after a dashboard update, or
after system speech but before an analytical action had completed. This
separation allowed us to distinguish \emph{what} changed in the investigation
from \emph{when} the user expressed the change.

The coders resolved disagreements by examining the preceding request, the
assistant's response, the current dashboard state, and the subsequent
interaction. The final paper should report
\textcolor{red}{[AGREEMENT PROCEDURE AND RELIABILITY, IF CALCULATED]}.

\subsection{Formative Findings}
\label{sec:formative-findings}

\subsubsection{Analytical goals were redirected as new questions emerged}

Goal shifts changed the knowledge outcome being pursued rather than merely the
next interface operation. In one episode, the prior interaction concerned
monthly order trends. The participant redirected the analysis toward customer
experience:

\begin{quote}
``Customer experience analysis---the low-rated orders, including their time,
category, and delivery conditions.''
\end{quote}

The utterance replaced an order-volume-oriented analysis with an investigation
of low ratings and their possible contributing factors. In another episode,
after exploring geographic delivery performance, a participant requested a
payment-method pie chart. Although the request contained a representation
choice, its analytical significance came from abandoning the logistics topic
and beginning an unrelated investigation of payment behavior.

Other goal shifts were more incremental. A participant moved from generally
comparing state-level product categories to actively seeking products with
unusually low ratings. Such episodes show that goal shifts may change the
topic, the desired form of knowledge, or the intended analytical outcome
without necessarily changing the dataset.

\subsubsection{Scope refinement occurred along several data dimensions}

Scope refinements preserved the broader analytical purpose while changing the
data target. Participants introduced geographic groupings, rating thresholds,
time intervals, product categories, and temporal granularity.

For example, after requesting an overall view of customer satisfaction, one
participant stated:

\begin{quote}
``First, let us look at the distribution by region.''
\end{quote}

The satisfaction objective remained active, but the relevant comparison was
reorganized around geographic regions. In another session, a participant
restricted the dashboard to one- and two-star orders and subsequently limited
the analysis to September 2017 through May 2018. These utterances successively
refined the rating and temporal scope while preserving the broader concern
with low-rating customer experience.

The logs also contained scope broadening, substitution, and changes in
granularity. Participants moved from one state to all states, replaced one
product category with another, and changed a monthly trend into a weekly
analysis. These cases motivated the term \emph{Scope Refinement} rather than
the narrower \emph{Scope Narrowing}.

A dashboard operation alone was not considered sufficient evidence of scope
revision. A filter could implement a previously established plan without
changing the intended scope of subsequent reasoning. Coding therefore depended
on the relationship between the operation and the prior analytical commitment.

\subsubsection{Working-hypothesis revision required an existing proposition}

Working-hypothesis episodes were less frequent and required stricter contextual
judgment. A statement such as ``AP is an outlier below the average'' may
establish an initial interpretation, but it constitutes revision only when it
qualifies or replaces an already active proposition.

A clearer case occurred when a participant questioned a state-prioritization
criterion based primarily on delivery time:

\begin{quote}
``BA only has the longest delivery time. Does this take sales volume into
account?''
\end{quote}

The utterance did not merely request another chart. It challenged the
sufficiency of the active proposition that Bahia should be prioritized because
of its delivery time and introduced sales volume as a condition that might
alter that conclusion. We coded such cases as qualification of a working
hypothesis or decision-relevant interpretation.

The candidate analysis also exposed a boundary between hypothesis revision
and method revision. One participant proposed combining delivery days and
order volume into a ratio. This changed the metric and analytical
operationalization used to evaluate states; it did not necessarily replace an
explanatory proposition. We therefore retained
\emph{Method or Operationalization Revision} as a residual code rather than
forcing every change in analytical reasoning into Working-Hypothesis Revision.

Similarly, asking ``Why is AP the lowest?'' moves from description toward
explanation but does not by itself revise a hypothesis if no prior explanation
has been adopted. Such an episode may represent an explanatory goal shift,
hypothesis formation, or a request for additional evidence depending on the
surrounding context.

\subsubsection{Compound revisions changed multiple analytical objects}

Eight candidate episodes received more than one revision label. For example, a
participant stated:

\begin{quote}
``Apply the same analysis to the third- through fifth-ranked states; I want to
find products with relatively low ratings.''
\end{quote}

The request simultaneously restricted the analysis to a subset of states and
redirected the purpose from general comparison to active anomaly seeking. We
therefore treated it as both Analytical Scope Refinement and Analytical Goal
Shift.

Compound episodes were not treated as coding errors or exceptional cases.
Instead, they showed that goal, working hypothesis, and scope are related but
distinguishable dimensions that can change together in one utterance. This
motivated multi-label coding and argues against implementing the three
constructs as mutually exclusive runtime intent classes.

\subsubsection{Revision had to be distinguished from repair and representation
change}

Some utterances that appeared to redirect the system were better understood as
repair. For example:

\begin{quote}
``I mean by state---state.''
\end{quote}

The utterance corrected a grounding or speech-recognition error between weekly
aggregation and state-level grouping. It restored the intended request rather
than expressing a newly developed analytical direction.

Representation changes were also context dependent. A request for a pie chart
could accompany a genuine goal shift when the user changed from delivery
analysis to payment behavior. In contrast, changing only the chart form for an
existing question would be coded as a method or representation change. The
latest utterance could therefore not be coded reliably without its prior
dialogue and dashboard context.

\subsubsection{Revision semantics and interruption timing were orthogonal}

Most candidate revisions occurred at ordinary turn boundaries or after a
dashboard update, while only a small number were detected after system speech
but before analytical completion. The formative evidence therefore supports
the occurrence of analytical revision during exploratory interaction, but does
not imply that revisions predominantly occur through barge-in.

Barge-in describes the temporal overlap between user and system speech.
Analytical revision describes the semantic relationship between a new
utterance and the active investigation. A user may interrupt to correct a
misrecognized term without changing the analysis, or may wait until the
assistant has finished before substantially redirecting the goal. The two
dimensions should therefore be modeled and evaluated separately.

\subsection{Design Requirements}
\label{sec:design-requirements}

The theoretical framing and formative findings informed four design
requirements.

\paragraph{DR1: Interpret new utterances relative to active analytical
commitments.}

The system should maintain sufficient dialogue and dashboard context to
determine whether a new request preserves, qualifies, or supersedes the active
goal, working interpretation, or scope. An utterance should not be interpreted
as an isolated command independent of the investigation that precedes it.

\paragraph{DR2: Support overlapping revisions through composable actions.}

A single utterance may redirect the analytical goal while simultaneously
changing several data constraints or qualifying an interpretation. The system
should therefore support composable, schema-grounded analytical actions rather
than require each utterance to map to one operation or one mutually exclusive
revision class.

\paragraph{DR3: Distinguish analytical revision from repair, evidence seeking,
and method change.}

Recognition corrections, clarification requests, requests for further
evidence, and changes in chart or metric should not automatically be treated
as changes to analytical intent. The system should preserve these distinctions
so that a repair restores the intended request and a method change does not
unnecessarily discard a still-valid analytical objective.

\paragraph{DR4: Coordinate supersession across speech, tools, and dashboard
state.}

In a full-duplex setting, a revised request may arrive while system speech,
tool generation, query execution, or dashboard rendering is still active.
When the new request supersedes the active response, obsolete speech should be
stopped, response-dependent analytical actions should be invalidated, late
results should be rejected, and replanning should begin from the latest
committed dashboard state.

This final requirement follows from combining the observed phenomenon of
analytical revision with concurrent system execution. It does not assume that
all revisions occur as barge-ins; rather, it specifies the additional
coordination needed when a revision does arrive before the current response
has completed.

\subsection{Scope of the Formative Evidence}
\label{sec:formative-scope}

The formative inquiry provides design-oriented evidence rather than validation
of a general taxonomy. Four participants cannot establish theoretical
saturation, estimate population-level frequencies, or demonstrate that the
three constructs cover all forms of analytical change. Moreover, the
LLM-assisted annotations were used for candidate retrieval and require human
verification against the original interaction context.

We therefore treat Analytical Goal Shift, Working-Hypothesis Revision, and
Analytical Scope Refinement as theory-informed, non-exhaustive, and potentially
overlapping analytical lenses. The formative evidence illustrates their
usefulness, exposes important compound and boundary cases, and informs the
design of VerbalVis. The subsequent user study evaluates the full-duplex
interaction and orchestration mechanisms rather than testing the three
constructs as a universal classification.
