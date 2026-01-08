---
attachments:
- documentId: 090166e5247239b0
  ersFileName: V4-PDF- VoxelSensors - BE -European XR Chip - 03112025 RC .pdf
  fileName: V4-PDF- VoxelSensors - BE -European XR Chip - 03112025 RC .pdf
  id: 27568665
  isExternalizedInHrs: true
  isRendered: true
  pages: 4
  pdfSize: 313260
  size: 310706
companySize: SMALL
country: BEL
dateFeedback: 2025/11/03 10:38:53
feedback: Hello, Please receive the feedback from VoxelSensors , a fabless semiconductor
  company form Brussels beneficiary of EIC Accekerstor .
firstName: Andre
id: 33112855
initiativeTitle: Evaluation and Revision of the Chips Act Chips Act 20
isDislikedByMe: false
isLikedByMe: false
isMyFeedback: false
language: EN
login: ''
organization: 'Voxelsensors '
publication: WITHINFO
publicationId: 20335
publicationStatus: CLOSED
referenceInitiative: Ares(2025)7293034
status: PUBLISHED
surname: Miodezky
userType: COMPANY
---

Ref. Ares(2025)9425160 - 03/11/2025

# Voxelsensors contribution. European XR Chip Implementation Plan (v4 – Policy Brief Edition)


VoxelSensors – Strategic Contribution to the European XR Ecosystem
Date: November 2025 – V4
Author: Andre Miodezky, Public Sector Manager – Ward van der Temple CTO

## **Executive Overview**

In our opinion Europe’s technological sovereignty in wearable and XR computing depends on its
ability to control the perception and sensor-fusion layer—the interface between the physical and
digital world. This document presents VoxelSensors’  recommendations to guide the European
Union programs toward a realistic and impactful direction. Rather than attempting to replicate fullscale mobile SoCs dominated by global incumbents, Europe should invest in specialized, eventdriven perception coprocessors leveraging existing regional strengths in SPAD/SPAES, ToF, RGB
and neuromorphic architectures. This approach ensures industrial competitiveness, accelerates
dual-use innovation, and strengthens Europe’s position in next-generation XR, robotics, spatial
computing and dual use.

## **1. Context and Rationale**

Europe urgently needs to consolidate its leadership in XR and wearable hardware sovereignty.
Current EU programs (e.g., Horizon Europe) fund fragmented subsystems, while global
competitors—Qualcomm, Apple, Samsung, Sony, and Huawei—control end-to-end XR platforms. A
European-made XR chip could serve as the technological anchor for a sustainable wearable
ecosystem, linking semiconductor innovation to product-level integration and AI-driven
applications. However, any such effort must extend beyond isolated IP blocks and instead fund the
entire value chain (design → manufacturing → software → integration).

## **2. Strategic Assessment**

Despite substantial research funding, Europe faces a persistent gap between R&D excellence and
industrial-scale commercialization. EU initiatives typically support individual components or subsystems rather than complete product ecosystems. This fragmented approach limits Europe’s
ability to compete globally in XR and AI hardware. To bridge this divide, a focused, sovereign XR


VoxelSensors 2025/03/11 contribution to European XR chip 1


initiative must combine innovation in semiconductor design with manufacturing, software, and
OEM integration capabilities.


The market context also demands realism. Replicating the business model of Qualcomm or Apple
would require decades of accumulated IP, complex software ecosystems, and multi-billion-euro
investments. These giant companies will also improve their current products with better and
cheaper solutions. Europe currently lacks the industrial scale for such an undertaking. Therefore, it
is strategically wiser to reinforce existing players by concentrating on next-generation, low-power,
perception-focused architectures that can integrate with global platforms.

## **3. Recommended Technological Approach**

Based on industry experience—including VoxelSensors’ direct integration work with Qualcomm
Snapdragon XR2—it is clear that the most viable path forward is the development of a European XR
Sensor-Fusion + AI Coprocessor (Option A) before advancing to a full standalone XR SoC (Option B).

### **3.1 Option A — XR Sensor-Fusion + AI Coprocessor (Recommended)**

- Purpose: Ultra-low-latency fusion of cameras (global shutter, ToF, SPAD/SPAES, event-based),
IMU, RGB, eye and hand tracking, and SLAM/VIO pipelines.

- Node: 22FDX (FD-SOI) or 16/12 nm FinFET (EU-based manufacturing).

- Interfaces: 4–6× CSI-2 (2.5–4 Gbps/lane), 1–2× DSI/eDP, LPDDR4x/LPDDR5 (32-bit),
PCIe Gen3 x1/x2, USB 3.x, I2C/SPI/UART; synchronized triggers and TSN-friendly time base.

- Accelerators: ISP pipeline (HDR, de-mosaic, denoise), DSP blocks for VIO, and small NPU (1–
5 TOPS INT8) optimized for edge AI inference with peak efficiency per watt.

- Power: < 2 W active typical, < 50 mW idle.

- Form Factor: SiP / fan-out WLP options, with EVK reference design for OEM partners.

### **3.2 Option B — Full XR SoC (Application Processor + GPU/NPU + Perception)**

- Purpose: A single-chip standalone XR platform (Qualcomm-class competitor).

- Node: 16/12 nm initially; 7 nm for Gen-2 (external foundry).

- Pros: Platform control and integration.

- Cons: Very high NRE, complex software stack, longer time-to-market, and uncertain ROI.
Option B should be considered only after validating market traction from Option A deployments.

## **4. Investment and Implementation Considerations**

A realistic funding framework should be based on stage-gated financing aligned with design and
tape-out milestones. The proposed structure includes:

- Core program (Option A coprocessor): ~€1 billion over 36–48 months.

- Integration and pilots with vendor hardware: €0.5 billion.

- Full wearable reference designs and industrial acceleration: €3 billion+.
This brings the potential total envelope to ~€4.5 billion, similar in scale to European Processor
Initiative (EPI) investments in HPC.


VoxelSensors 2025/03/11 contribution to European XR chip 2


Primary risks include market scalability, software ecosystem complexity, and fabrication yield.
Mitigation strategies involve multi-vertical attachment (XR, robotics, industrial wearables, dual
use) and early SDK and partner pilot programs.


Annex 1 shows main XR players investments table.

## **5. Strategic Implications and Policy Alignment**

This initiative directly supports the objectives of the EU Chips Act, IPCEI, and Web 4.0 / Virtual
Worlds strategies. It complements ongoing Horizon Europe projects (e.g., PERCEIVE, SPEAR) that
emphasize human-centric computing, spatial AI, and ultra-efficient data fusion. By focusing on
perception coprocessors, Europe can ensure that its know-how remains embedded in the core of
global XR devices even when using foreign main processors.


This asymmetric strategy allows Europe to own the intelligence at the edge, ensuring technological
sovereignty without duplicating massive industrial ecosystems already dominated by U.S. and
Asian players.

## **6. Conclusion and Recommendations**

Europe should pursue a leapfrog strategy based on neuromorphic and event-driven architectures
—areas that match its strengths in RGB, Global Shuter, SPAD, SPAES, and ToF sensor innovation.
Instead of replicating U.S. or Asian SoCs, Europe can establish global leadership in the perception
layer of XR and AI systems. The approach not only enhances European autonomy but also creates a
scalable industrial base for XR, robotics, dual use and Physical AI markets.


The recommended first step is the launch of a European XR Sensor-Fusion Coprocessor Program,
co-funded under the EU Chips Act and national innovation agencies, targeting first silicon within
36 months. This initiative would secure Europe’s foothold in the next wave of spatial and empathic
computing.


VoxelSensors 2025/03/11 contribution to European XR chip 3


Annexe 1/ VR/XR/AR Investment Summary (2020-2025)


Meta has invested more than all other companies combined:

- Meta: ~$80-100 billion

- All competitors combined: ~$15-30 billion


VoxelSensors 2025/03/11 contribution to European XR chip 4


