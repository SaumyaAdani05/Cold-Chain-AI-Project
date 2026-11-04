;; problem.pddl - scenario 1: normal transport of one frozen vaccine package.
;; Matches scenarios.py: normal_single_vaccine (package P1, needs dry ice,
;; simulated readings inside -80 C to -60 C).
;; The time budget (120 min) and dry-ice stock (10 kg, 2 kg per package)
;; are enforced by the Python constraint layer, not by this file.

(define (problem normal-single-vaccine)
  (:domain cold-chain)

  (:objects
    p1 - package
  )

  (:init
    (at-gate p1)
    (container-open p1)
    (temp-in-range p1)
    (needs-dry-ice p1)
  )

  (:goal
    (and (loaded p1))
  )
)
