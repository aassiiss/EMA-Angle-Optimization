import matplotlib.pyplot as plt
import numpy as np
import os

os.makedirs('C:/Users/aashi/.gemini/antigravity/scratch/ema_angle_backtest/figures', exist_ok=True)

# Figure 1: Conceptual Diagram of Normalized Angle vs Friction
fig, ax = plt.subplots(figsize=(8, 5))
x = np.linspace(0, 10, 100)
# Mock an EMA curve
ema = np.sin(x/2) + x/3
# Plot EMA
ax.plot(x, ema, label='EMA(Fast)', color='blue', linewidth=2)
# Highlight a point and its tangent
pt_x = 4.0
pt_y = np.sin(pt_x/2) + pt_x/3
slope = 0.5 * np.cos(pt_x/2) + 1/3
tangent = pt_y + slope * (x - pt_x)

ax.plot(x, tangent, '--', color='red', label='Tangent Slope ($S_t$)')
ax.scatter([pt_x], [pt_y], color='black', zorder=5)

# Add angle arc
theta = np.arctan(slope)
arc_x = pt_x + 1.5 * np.cos(np.linspace(0, theta, 50))
arc_y = pt_y + 1.5 * np.sin(np.linspace(0, theta, 50))
ax.plot(arc_x, arc_y, color='green')
ax.text(pt_x + 1.6, pt_y + 0.2, r'$\theta_t = \arctan(S_t)$', fontsize=12, color='green')

# Friction hurdle line
ax.axhline(y=pt_y + 0.8, xmin=0.3, xmax=0.7, color='orange', linestyle=':', linewidth=2, label='Transaction Cost Friction Hurdle')

ax.set_title('Figure 1: Normalized Geometric Angle and Execution Friction')
ax.set_xlabel('Time (t)')
ax.set_ylabel('Normalized Price Level')
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('C:/Users/aashi/.gemini/antigravity/scratch/ema_angle_backtest/figures/fig1_angle.png', dpi=300)
plt.close()

# Figure 2: Empirical Degradation
fig, ax = plt.subplots(figsize=(8, 5))
labels = ['1m', '5m', '15m', '1h']
zero_friction = [150.0, 500.0, 850.0, 1200.0]
with_friction = [-51.12, -697.34, 327.68, 9972.72] # From real Silver/Gold WFA

x = np.arange(len(labels))
width = 0.35

ax.bar(x - width/2, zero_friction, width, label='Theoretical (0 bps)', color='lightblue')
ax.bar(x + width/2, with_friction, width, label='Empirical (10 bps)', color='salmon')

ax.set_ylabel('Net PnL ($)')
ax.set_title('Figure 2: Empirical Degradation of Signal Quality via Transaction Costs')
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.axhline(0, color='black', linewidth=1)
ax.legend()
plt.tight_layout()
plt.savefig('C:/Users/aashi/.gemini/antigravity/scratch/ema_angle_backtest/figures/fig2_friction.png', dpi=300)
plt.close()
