;; domain.pddl - STRIPS-style PDDL domain for automated cold-chain logistics.
;;
;; This file mirrors the operators in actions.py. It documents the planning
;; model in standard PDDL form. The project's own BFS and POP planners work
;; on the Python version, which is the one that is tested and executed.
;;
;; Classic STRIPS has no numbers, so the following are NOT modelled here and
;; are checked by the Python constraint layer (constraints.py):
;;   * action durations and the total time budget,
;;   * the dry-ice stock and the dry-ice consumption per package,
;;   * the simulated temperature readings (only their outcome is encoded, as
;;     the predicate temp-in-range).
;;
;; The predicate ice-ready is a STRIPS trick. It stands for "the package's
;; ice requirement is satisfied". Frozen packages get it from pack-dry-ice.
;; Refrigerated packages start with it in the problem file, so they never
;; need dry ice. This lets one seal-container action serve both kinds of
;; package without negative preconditions.

(define (domain cold-chain)
  (:requirements :strips :typing)

  (:types package)

  (:predicates
    (at-gate ?p - package)               ; package waits at the gate
    (at-receiving ?p - package)          ; package is on the receiving bay
    (temp-in-range ?p - package)         ; simulated readings are inside the range
    (temp-verified ?p - package)         ; temperature has been verified
    (at-cold-room ?p - package)          ; package is in the cold room
    (container-open ?p - package)        ; container is not yet sealed
    (dry-ice-packed ?p - package)        ; dry ice has been put in the container
    (ice-ready ?p - package)             ; ice requirement is satisfied
    (container-inspected ?p - package)   ; container has been inspected
    (container-sealed ?p - package)      ; container is sealed
    (at-dock ?p - package)               ; package is at the loading dock
    (loaded ?p - package)                ; package is on the delivery pallet
    (needs-dry-ice ?p - package)         ; frozen product (static fact)
  )

  (:action receive-package
    :parameters (?p - package)
    :precondition (at-gate ?p)
    :effect (and (not (at-gate ?p)) (at-receiving ?p)))

  (:action verify-temperature
    :parameters (?p - package)
    :precondition (and (at-receiving ?p) (temp-in-range ?p))
    :effect (temp-verified ?p))

  (:action move-to-cold-room
    :parameters (?p - package)
    :precondition (and (at-receiving ?p) (temp-verified ?p))
    :effect (and (not (at-receiving ?p)) (at-cold-room ?p)))

  (:action pack-dry-ice
    :parameters (?p - package)
    :precondition (and (needs-dry-ice ?p) (at-cold-room ?p) (container-open ?p))
    :effect (and (dry-ice-packed ?p) (ice-ready ?p)))

  (:action inspect-container
    :parameters (?p - package)
    :precondition (and (at-cold-room ?p) (container-open ?p))
    :effect (container-inspected ?p))

  (:action seal-container
    :parameters (?p - package)
    :precondition (and (container-inspected ?p) (container-open ?p) (ice-ready ?p))
    :effect (and (not (container-open ?p)) (container-sealed ?p)))

  (:action move-to-loading-dock
    :parameters (?p - package)
    :precondition (and (at-cold-room ?p) (container-sealed ?p))
    :effect (and (not (at-cold-room ?p)) (at-dock ?p)))

  (:action load-pallet
    :parameters (?p - package)
    :precondition (and (at-dock ?p) (container-sealed ?p))
    :effect (and (not (at-dock ?p)) (loaded ?p)))
)
